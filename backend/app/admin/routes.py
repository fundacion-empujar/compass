import logging
import os
from datetime import timedelta
from http import HTTPStatus
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.admin.types import (
    CreateRegistrationLinkRequest,
    CreateRegistrationLinkResponse,
    CreateSharedCodeRequest,
    CreateSharedCodeResponse,
)
from app.constants.errors import HTTPErrorResponse
from app.invitations.repository import UserInvitationRepository
from app.invitations.types import UserInvitation
from app.server_dependencies.db_dependencies import CompassDBProvider
from app.users.auth import Authentication, require_super_admin
from common_libs.time_utilities import get_now

logger = logging.getLogger(__name__)

# HashRouter: the registration screen is served at <FRONTEND_URL>/#/register
_REGISTER_LINK_TEMPLATE = "{frontend_url}/#/register?{query}"
_DEFAULT_SHARED_CODE_VALIDITY_DAYS = 365


async def _get_user_invitation_repository(
    db: AsyncIOMotorDatabase = Depends(CompassDBProvider.get_application_db),
) -> UserInvitationRepository:
    return UserInvitationRepository(db)


def add_admin_routes(app: FastAPI, authentication: Authentication):
    """Mount the staff admin endpoints. Every route is gated on the Firebase
    ``super_admin`` custom claim via the router-level dependency, so the API
    Gateway enforces a logged-in super-admin across the whole ``/admin`` surface."""

    router = APIRouter(
        prefix="/admin",
        tags=["admin"],
        dependencies=[Depends(require_super_admin(authentication))],
    )

    @router.post(
        path="/registration-links",
        response_model=CreateRegistrationLinkResponse,
        responses={500: {"model": HTTPErrorResponse}},
        name="create per-student registration link",
        description="Assemble a shareable secure registration link for one student. "
                    "Stateless — nothing is stored until the student registers.",
    )
    async def _create_registration_link(
        body: CreateRegistrationLinkRequest,
        invitations_repository: UserInvitationRepository = Depends(_get_user_invitation_repository),
    ) -> CreateRegistrationLinkResponse:
        registration_code = body.registration_code.strip()
        if not registration_code:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="registration_code is required")

        # Assemble server-side so SEC_TOKEN never ships in frontend code.
        frontend_url = (os.getenv("FRONTEND_URL") or "").rstrip("/")
        sec_token = os.getenv("SEC_TOKEN")
        if not frontend_url or not sec_token:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail="Registration links are not configured (FRONTEND_URL / SEC_TOKEN missing)",
            )

        query = urlencode({"reg_code": registration_code, "report_token": sec_token})
        link = _REGISTER_LINK_TEMPLATE.format(frontend_url=frontend_url, query=query)

        existing_claim = await invitations_repository.get_claim_by_registration_code(registration_code)
        return CreateRegistrationLinkResponse(
            registration_code=registration_code,
            link=link,
            already_used=existing_claim is not None,
        )

    @router.post(
        path="/shared-codes",
        response_model=CreateSharedCodeResponse,
        status_code=HTTPStatus.CREATED,
        responses={500: {"model": HTTPErrorResponse}},
        name="create shared invitation code",
        description="Create (or update) a shared invitation code that many people can use.",
    )
    async def _create_shared_code(
        body: CreateSharedCodeRequest,
        invitations_repository: UserInvitationRepository = Depends(_get_user_invitation_repository),
    ) -> CreateSharedCodeResponse:
        invitation_code = body.invitation_code.strip()
        if not invitation_code:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invitation_code is required")

        now = get_now()
        valid_from = body.valid_from or now
        valid_until = body.valid_until or (now + timedelta(days=_DEFAULT_SHARED_CODE_VALIDITY_DAYS))
        if valid_until <= valid_from:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="valid_until must be after valid_from")

        invitation = UserInvitation(
            invitation_code=invitation_code,
            allowed_usage=body.allowed_usage,
            remaining_usage=body.allowed_usage,
            valid_from=valid_from,
            valid_until=valid_until,
            invitation_type=body.invitation_type,
            sensitive_personal_data_requirement=body.sensitive_personal_data_requirement,
        )
        await invitations_repository.upsert_many_invitations([invitation])
        logger.info("Shared invitation code created/updated: %s (%s)", invitation_code, body.invitation_type)

        return CreateSharedCodeResponse(
            invitation_code=invitation_code,
            invitation_type=invitation.invitation_type,
            allowed_usage=invitation.allowed_usage,
            valid_from=valid_from,
            valid_until=valid_until,
            sensitive_personal_data_requirement=invitation.sensitive_personal_data_requirement,
        )

    app.include_router(router)
