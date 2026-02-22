"""Authentication and password schemas."""

from pydantic import BaseModel, Field


class SignInSchema(BaseModel):
    Company_Portal_Url: str
    username: str
    password: str


class ResetPasswordSchema(BaseModel):
    Company_Shortname: str
    Username: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class UpdatePassword(BaseModel):
    Company_Portal_Url: str
    old_password: str
    new_password: str


class ForgotPassword(BaseModel):
    Company_Portal_Url: str
    Email: str


class resendSchema(BaseModel):
    Company_Portal_Url: str
    email: str


class otpSchema(BaseModel):
    token: str
    email: str
    Company_Portal_Url: str
