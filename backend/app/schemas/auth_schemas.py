from datetime import datetime

from pydantic import BaseModel


class AuthCallbackResponse(BaseModel):
    success: bool
    shop: str
    access_mode: str
    message: str


class ShopInstallationOut(BaseModel):
    shop_domain: str
    access_mode: str
    scope: str | None
    associated_user_id: str | None
    masked_access_token: str
    installed_at: datetime
    updated_at: datetime
    is_active: bool


class ShopInstallationsResponse(BaseModel):
    shop: str
    records: list[ShopInstallationOut]
