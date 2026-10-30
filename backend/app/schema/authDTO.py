from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    captcha_id: str = Field(
        min_length=1,
        max_length=64,
        description="验证码 ID",
    )
    captcha_code: str = Field(
        min_length=1,
        max_length=8,
        description="验证码字符",
    )


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_id: str = Field(
        min_length=1,
        max_length=64,
        description="验证码 ID",
    )
    captcha_code: str = Field(
        min_length=1,
        max_length=8,
        description="验证码字符",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 有效期（秒）


class TokenPayload(BaseModel):
    """JWT 载荷中承载的用户身份。"""

    user_id: int
    username: str
    role: str
