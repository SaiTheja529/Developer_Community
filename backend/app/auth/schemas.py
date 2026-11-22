from __future__ import annotations

from pydantic import EmailStr, Field

from app.common.validation import StrictModel, Text


class RegisterBody(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    username: Text(1, 60)
    display_name: Text(1, 60)


class LoginBody(StrictModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenBody(StrictModel):
    token: str = Field(min_length=1, max_length=200)


class ForgotPasswordBody(StrictModel):
    email: str = Field(min_length=1, max_length=320)


class ResetPasswordBody(StrictModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePasswordBody(StrictModel):
    # Optional only for accounts that sign in with GitHub/Google and have no password yet.
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ChangeEmailBody(StrictModel):
    new_email: EmailStr
    password: str | None = Field(default=None, max_length=256)


class DeleteAccountBody(StrictModel):
    password: str | None = Field(default=None, max_length=256)
