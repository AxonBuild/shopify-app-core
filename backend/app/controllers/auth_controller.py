from fastapi import Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.engine import get_db
from app.database.repositories.shop_installation_repository import ShopInstallationRepository
from app.schemas.auth_schemas import (
    ShopInstallationOut,
    ShopInstallationsResponse,
)
from app.services.shopify_auth_service import shopify_auth_service
from app.utils.logger import get_logger
from app.utils.security import is_valid_shop_domain, mask_token

logger = get_logger(__name__)


class AuthController:
    async def install(self, shop: str, access_mode: str = "offline") -> RedirectResponse:
        logger.info("install — shop=%s access_mode=%s", shop, access_mode)
        url = shopify_auth_service.build_install_url(shop=shop, access_mode=access_mode)
        logger.debug("install — redirecting to Shopify OAuth URL for shop=%s", shop)
        return RedirectResponse(url=url, status_code=302)

    async def callback(
        self,
        query_params: dict[str, str],
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        shop = query_params.get("shop", "<unknown>")
        logger.info("callback — shop=%s", shop)

        shop_result, access_mode = await shopify_auth_service.handle_callback(query_params, db)

        logger.info(
            "callback complete — shop=%s access_mode=%s", shop_result, access_mode
        )

        # Redirect the merchant to the post-install destination.
        # Update POST_INSTALL_REDIRECT_URL in .env when your real frontend is ready.
        redirect_url = f"{settings.post_install_redirect_url.rstrip('/')}?shop={shop_result}"
        logger.info("callback — redirecting to %s", redirect_url)
        return RedirectResponse(url=redirect_url, status_code=302)

    async def get_shop_connection(
        self, shop: str, db: Session = Depends(get_db)
    ) -> ShopInstallationsResponse:
        logger.info("get_shop_connection — shop=%s", shop)

        if not is_valid_shop_domain(shop):
            logger.warning("get_shop_connection rejected — invalid domain: %s", shop)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid shop domain format.",
            )

        repo = ShopInstallationRepository(db)
        records = repo.get_by_shop(shop)

        logger.debug(
            "get_shop_connection — shop=%s records_found=%d", shop, len(records)
        )

        items = [
            ShopInstallationOut(
                shop_domain=r.shop_domain,
                access_mode=r.access_mode,
                scope=r.scope,
                associated_user_id=r.associated_user_id,
                masked_access_token=mask_token(r.access_token),
                installed_at=r.installed_at,
                updated_at=r.updated_at,
                is_active=r.is_active,
            )
            for r in records
        ]
        return ShopInstallationsResponse(shop=shop, records=items)
