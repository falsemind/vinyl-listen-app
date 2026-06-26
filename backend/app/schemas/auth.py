from datetime import datetime

from pydantic import BaseModel, Field


class AuthErrorResponse(BaseModel):
    error: dict[str, str]


class RegisterAccountRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)


class RegisterAccountResponse(BaseModel):
    user_id: str
    email: str
    verification_expires_at: datetime


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=1, max_length=32)


class UserAccountResponse(BaseModel):
    user_id: str
    email: str
    email_verified_at: datetime | None


class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResendVerificationResponse(BaseModel):
    user_id: str
    email: str
    verification_expires_at: datetime
    resend_count: int


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    device_label: str | None = Field(default=None, max_length=120)


class TokenPairResponse(BaseModel):
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    token_type: str = "Bearer"
    session_id: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class PasswordResetRequestRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetRequestResponse(BaseModel):
    accepted: bool
    email: str


class PasswordResetConfirmRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=1024)


class PasswordResetConfirmCurrentRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=1024)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)
    sign_out_everywhere: bool = False


class PasswordChangeResponse(BaseModel):
    changed: bool
    revoked_sessions: int


class LogoutResponse(BaseModel):
    revoked: bool


class LogoutAllResponse(BaseModel):
    revoked_sessions: int


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class DeleteAccountResponse(BaseModel):
    deleted: bool
    deletion_receipt_id: str
    deleted_at: datetime


class DeleteAccountDataRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class DeleteAccountDataResponse(BaseModel):
    reset: bool
    reset_receipt_id: str
    reset_at: datetime
