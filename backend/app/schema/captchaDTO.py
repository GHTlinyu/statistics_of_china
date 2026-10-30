"""验证码接口的响应结构。"""

from pydantic import BaseModel, Field


class CaptchaDTO(BaseModel):
    captcha_id: str = Field(description="验证码 ID，登录 / 注册时回传")
    image: str = Field(description="PNG data URL")
    expires_in: int = Field(description="有效期（秒）")
