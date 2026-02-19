from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.engine import Base


class ShopInstallation(Base):
    __tablename__ = "shop_installations"
    __table_args__ = (UniqueConstraint("shop_domain", "access_mode", name="uq_shop_mode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shop_domain: Mapped[str] = mapped_column(String(255), index=True)
    access_mode: Mapped[str] = mapped_column(String(20), default="offline")
    access_token: Mapped[str] = mapped_column(String(500))
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    associated_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
