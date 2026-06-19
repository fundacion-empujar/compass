from datetime import datetime

from pydantic import BaseModel, Field

from app.invitations.types import InvitationType
from app.users.sensitive_personal_data.types import SensitivePersonalDataRequirement


class CreateRegistrationLinkRequest(BaseModel):
    registration_code: str = Field(..., min_length=1, description="Per-student code, e.g. a Salesforce Contact ID")
    invitation_code_template: str | None = Field(
        default=None, description="Optional shared invitation_code whose config the registration inherits"
    )


class CreateRegistrationLinkResponse(BaseModel):
    registration_code: str
    link: str
    already_used: bool
    """True if a registration has already been claimed under this code."""


class CreateSharedCodeRequest(BaseModel):
    invitation_code: str = Field(..., min_length=1, description="The shared code that many people can use")
    invitation_type: InvitationType
    allowed_usage: int = Field(default=999999, ge=1, description="How many people can use the code")
    valid_from: datetime | None = Field(default=None, description="Defaults to now")
    valid_until: datetime | None = Field(default=None, description="Defaults to one year from now")
    sensitive_personal_data_requirement: SensitivePersonalDataRequirement = SensitivePersonalDataRequirement.NOT_AVAILABLE


class CreateSharedCodeResponse(BaseModel):
    invitation_code: str
    invitation_type: InvitationType
    allowed_usage: int
    valid_from: datetime
    valid_until: datetime
    sensitive_personal_data_requirement: SensitivePersonalDataRequirement
