from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.shop_installation import ShopInstallation
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ShopInstallationRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self,
        *,
        shop_domain: str,
        access_mode: str,
        access_token: str,
        scope: str | None,
        associated_user_id: str | None,
    ) -> ShopInstallation:
        stmt = select(ShopInstallation).where(
            ShopInstallation.shop_domain == shop_domain,
            ShopInstallation.access_mode == access_mode,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            logger.info(
                "upsert — updating existing installation: shop=%s access_mode=%s scope=%s",
                shop_domain,
                access_mode,
                scope,
            )
            existing.access_token = access_token
            existing.scope = scope
            existing.associated_user_id = associated_user_id
            existing.is_active = True
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            logger.debug("upsert — update committed for shop=%s access_mode=%s", shop_domain, access_mode)
            return existing

        logger.info(
            "upsert — creating new installation: shop=%s access_mode=%s scope=%s",
            shop_domain,
            access_mode,
            scope,
        )
        installation = ShopInstallation(
            shop_domain=shop_domain,
            access_mode=access_mode,
            access_token=access_token,
            scope=scope,
            associated_user_id=associated_user_id,
            is_active=True,
        )
        self.db.add(installation)
        self.db.commit()
        self.db.refresh(installation)
        logger.debug("upsert — insert committed for shop=%s access_mode=%s", shop_domain, access_mode)
        return installation

    def get_by_shop(self, shop_domain: str) -> list[ShopInstallation]:
        stmt = (
            select(ShopInstallation)
            .where(ShopInstallation.shop_domain == shop_domain)
            .order_by(ShopInstallation.access_mode.asc())
        )
        results = list(self.db.execute(stmt).scalars().all())
        logger.debug(
            "get_by_shop — shop=%s records_returned=%d", shop_domain, len(results)
        )
        return results
