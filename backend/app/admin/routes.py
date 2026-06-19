import csv
import io
import logging
import os
from datetime import timedelta
from http import HTTPStatus
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.admin.auth import require_admin_token
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
from app.users.get_user_preferences_repository import get_user_preferences_repository
from app.users.repositories import IUserPreferenceRepository
from common_libs.time_utilities import get_now

logger = logging.getLogger(__name__)

# HashRouter: the registration screen is served at <FRONTEND_URL>/#/register
_REGISTER_LINK_TEMPLATE = "{frontend_url}/#/register?{query}"
_EXPORT_PAGE_SIZE = 200
_DEFAULT_SHARED_CODE_VALIDITY_DAYS = 365
# Staff-facing CSV (Spanish headers; the audience is es-AR Empujar staff). We expose a single
# "Código usado" column (invitation_code is always filled) plus a derived Tipo, instead of the
# confusing invitation_code/registration_code pair that staff couldn't tell apart.
_EXPORT_COLUMNS = ["ID de usuario", "Código usado", "Tipo", "Fecha de registro"]
_REGISTRATION_TYPE_INDIVIDUAL = "Individual"
_REGISTRATION_TYPE_GROUP = "Grupo"
# A cell starting with one of these is treated as a formula by Excel/Sheets. invitation_code is
# user-influenced and the export opens in a spreadsheet, so neutralize formula injection.
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    if value and value[0] in _CSV_FORMULA_PREFIXES:
        return "'" + value
    return value


async def _get_user_invitation_repository(
    db: AsyncIOMotorDatabase = Depends(CompassDBProvider.get_application_db),
) -> UserInvitationRepository:
    return UserInvitationRepository(db)


def add_admin_routes(app: FastAPI):
    """Mount the staff admin endpoints. Every route is gated by ADMIN_TOKEN via the
    router-level ``require_admin_token`` dependency (so the ``?token=`` query param is
    required and documented on each one)."""

    router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])

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

    @router.get(
        path="/registrations/export",
        name="export registrations as CSV",
        description="Stream a CSV of who registered with which code "
                    "(the code each person used, plus whether it was an individual or group code).",
    )
    async def _export_registrations(
        user_preferences_repository: IUserPreferenceRepository = Depends(get_user_preferences_repository),
    ) -> StreamingResponse:
        async def _generate_csv():
            header = io.StringIO()
            csv.writer(header).writerow(_EXPORT_COLUMNS)
            # UTF-8 BOM so Excel opens the Spanish headers/accents correctly.
            yield "﻿" + header.getvalue()

            try:
                async for batch in user_preferences_repository.stream_user_preferences(
                    page_size=_EXPORT_PAGE_SIZE, started_before=None, started_after=None
                ):
                    buffer = io.StringIO()
                    writer = csv.writer(buffer)
                    for pref in batch:
                        # Only rows that registered via a code carry reconciliation value.
                        if not (pref.registration_code or pref.invitation_code):
                            continue
                        # registration_code set ⇒ a per-student tracking link (Individual);
                        # otherwise the person used a shared group code (Grupo).
                        registration_type = (
                            _REGISTRATION_TYPE_INDIVIDUAL if pref.registration_code else _REGISTRATION_TYPE_GROUP
                        )
                        writer.writerow([
                            _csv_safe(pref.user_id or ""),
                            _csv_safe(pref.invitation_code or pref.registration_code or ""),
                            registration_type,
                            pref.accepted_tc.isoformat() if pref.accepted_tc else "",
                        ])
                    yield buffer.getvalue()
            except Exception:
                # Status 200 + headers were already sent when streaming began, so this can't become
                # an error response. Log it (a truncated export is otherwise silent) and propagate so
                # the client's download fails visibly instead of looking complete.
                logger.exception("Failed while streaming the registrations export (CSV truncated)")
                raise

        return StreamingResponse(
            _generate_csv(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=registrations.csv",
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff",
            },
        )

    app.include_router(router)
