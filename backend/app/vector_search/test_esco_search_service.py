import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.vector_search.esco_entities import OccupationEntity
from app.vector_search.esco_search_service import (
    SkillSearchService,
    OccupationSkillSearchService,
    _skills_of_occupation_cache,
)
from common_libs.environment_settings.constants import EmbeddingConfig
from conftest import random_db_name


class TestSkillSearchService:
    def test_to_entity_uses_skillId_field(self):
        # GIVEN a document returned from aggregation with skillId
        doc = {
            "skillId": "68f1da5290ad734984f7cb46",
            "modelId": "model",
            "UUID": "uuid-1",
            "preferredLabel": "child label",
            "description": "desc",
            "scopeNote": "scope",
            "originUUID": "origin",
            "UUIDHistory": ["uuid-1"],
            "altLabels": ["alt"],
            "skillType": "skill/competence",
            "score": 0.5,
        }

        # WHEN converting to a SkillEntity (constructor bypassed)
        service = SkillSearchService.__new__(SkillSearchService)
        entity = SkillSearchService._to_entity(service, doc)

        # THEN id is populated from skillId so downstream mapping works
        assert entity.id == "68f1da5290ad734984f7cb46"

    def test_to_entity_falls_back_to__id(self):
        # GIVEN a grouped document where _id carries the skill id
        doc = {
            "_id": "68f1da5290ad734984f7cb46",
            "modelId": "model",
            "UUID": "uuid-1",
            "preferredLabel": "child label",
            "description": "desc",
            "scopeNote": "scope",
            "originUUID": "origin",
            "UUIDHistory": ["uuid-1"],
            "altLabels": ["alt"],
            "skillType": "skill/competence",
            "score": 0.5,
        }

        service = SkillSearchService.__new__(SkillSearchService)
        entity = SkillSearchService._to_entity(service, doc)

        assert entity.id == "68f1da5290ad734984f7cb46"


# --- Helpers for the aggregation-pipeline tests ----------------------------------

def _skill_embedding_docs(model_id: ObjectId, skill_id: ObjectId, label: str, skill_type: str):
    # Mirror real data: each skill has 3 embedding docs that share identical metadata
    # and differ only in the embedding fields the pipeline strips out.
    return [
        {
            "modelId": model_id,
            "skillId": skill_id,
            "UUID": f"uuid-{skill_id}",
            "preferredLabel": label,
            "description": f"{label} description",
            "scopeNote": f"{label} scope",
            "originUUID": f"origin-{skill_id}",
            "UUIDHistory": [f"uuid-{skill_id}"],
            "altLabels": [f"{label} alt"],
            "skillType": skill_type,
            "embedded_field": field,
            "embedded_text": label,
            "embedding": [0.1, 0.2, 0.3],
        }
        for field in ("preferredLabel", "description", "altLabels")
    ]


def _relation(model_id: ObjectId, occupation_id: ObjectId, skill_id: ObjectId,
              relation_type: str, signalling: str = ""):
    return {
        "modelId": model_id,
        "requiringOccupationId": occupation_id,
        "requiredSkillId": skill_id,
        "relationType": relation_type,
        "signallingValueLabel": signalling,
    }


def _make_service(db: AsyncIOMotorDatabase, model_id: ObjectId) -> OccupationSkillSearchService:
    # Bypass the constructor: _find_skills_of_occupation only needs these three attributes.
    service = OccupationSkillSearchService.__new__(OccupationSkillSearchService)
    service._model_id = model_id
    service.embedding_config = EmbeddingConfig()
    service.relations_collection = db.get_collection(
        EmbeddingConfig().occupation_to_skill_collection_name)
    return service


def _occupation(occupation_id: ObjectId, model_id: ObjectId) -> OccupationEntity:
    return OccupationEntity(
        id=str(occupation_id), modelId=str(model_id), code="1234.5",
        UUID="occ-uuid", preferredLabel="Some occupation", altLabels=[],
        description="desc", score=0.0,
    )


@pytest.fixture(scope="function")
def in_memory_db(in_memory_mongo_server) -> AsyncIOMotorDatabase:
    # The motor client constructor is synchronous; only its operations are awaited.
    return AsyncIOMotorClient(
        in_memory_mongo_server.connection_string,
        tlsAllowInvalidCertificates=True,
    ).get_database(random_db_name())


@pytest.mark.asyncio
class TestFindSkillsOfOccupation:
    """Covers the optimized aggregation in OccupationSkillSearchService._find_skills_of_occupation."""

    async def test_collapses_triplicate_skill_docs_and_maps_fields(
            self, in_memory_db: AsyncIOMotorDatabase):
        # GIVEN two skills, each stored as 3 embedding docs, both linked to one occupation
        await _skills_of_occupation_cache.clear()
        db = in_memory_db
        cfg = EmbeddingConfig()
        model_id, occupation_id = ObjectId(), ObjectId()
        skill_a, skill_b = ObjectId(), ObjectId()

        await db.get_collection(cfg.skill_collection_name).insert_many(
            _skill_embedding_docs(model_id, skill_a, "Python", "skill/competence")
            + _skill_embedding_docs(model_id, skill_b, "Teamwork", "attitude"))
        await db.get_collection(cfg.occupation_to_skill_collection_name).insert_many([
            _relation(model_id, occupation_id, skill_a, "essential", "high"),
            _relation(model_id, occupation_id, skill_b, "optional"),
        ])

        # WHEN finding the skills of the occupation
        service = _make_service(db, model_id)
        result = await service._find_skills_of_occupation(_occupation(occupation_id, model_id))

        # THEN each skill appears exactly once (3 docs collapsed to 1) with its fields mapped
        assert len(result) == 2
        by_id = {entity.id: entity for entity in result}
        assert by_id[str(skill_a)].preferredLabel == "Python"
        assert by_id[str(skill_a)].skillType == "skill/competence"
        assert by_id[str(skill_a)].relationType == "essential"
        assert by_id[str(skill_a)].signallingValueLabel == "high"
        assert by_id[str(skill_b)].relationType == "optional"

    async def test_relation_without_matching_skill_is_skipped(
            self, in_memory_db: AsyncIOMotorDatabase):
        # GIVEN one valid relation and one dangling relation (no matching skill doc)
        await _skills_of_occupation_cache.clear()
        db = in_memory_db
        cfg = EmbeddingConfig()
        model_id, occupation_id = ObjectId(), ObjectId()
        skill_a = ObjectId()

        await db.get_collection(cfg.skill_collection_name).insert_many(
            _skill_embedding_docs(model_id, skill_a, "Python", "skill/competence"))
        await db.get_collection(cfg.occupation_to_skill_collection_name).insert_many([
            _relation(model_id, occupation_id, skill_a, "essential"),
            _relation(model_id, occupation_id, ObjectId(), "optional"),  # dangling
        ])

        # WHEN finding the skills — the dangling relation must be dropped, not raise
        service = _make_service(db, model_id)
        result = await service._find_skills_of_occupation(_occupation(occupation_id, model_id))

        # THEN only the matched skill is returned
        assert [entity.id for entity in result] == [str(skill_a)]

    async def test_raises_when_occupation_belongs_to_another_model(
            self, in_memory_db: AsyncIOMotorDatabase):
        # GIVEN an occupation whose modelId does not match the service's model
        await _skills_of_occupation_cache.clear()
        service = _make_service(in_memory_db, ObjectId())
        occupation = _occupation(ObjectId(), ObjectId())  # different model id

        # WHEN/THEN finding its skills raises
        with pytest.raises(ValueError):
            await service._find_skills_of_occupation(occupation)
