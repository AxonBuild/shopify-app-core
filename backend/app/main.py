import logging
import sys

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config.settings import settings
from app.database.engine import Base, engine, get_db
from app.database.models import ShopInstallation  # noqa: F401
from app.database.repositories.shop_installation_repository import ShopInstallationRepository
from app.middleware.request_logging import log_requests_middleware
from app.routes.auth_routes import router as auth_router
from app.services.shopify_auth_service import shopify_auth_service
from app.utils.logger import get_logger
from sqlalchemy.orm import Session


def _configure_logging() -> None:
    """Set up a structured, human-readable log format for the whole app.

    Format example::

        2026-02-19 10:33:19,123 | INFO     | app.services.shopify_auth_service:42 | Install URL built for my-shop.myshopify.com
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    # Avoid duplicate handlers if create_app() is called more than once (e.g. tests)
    if not root.handlers:
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)

    # Quiet down noisy third-party loggers unless we're in DEBUG mode
    if log_level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    _configure_logging()

    logger = get_logger(__name__)
    logger.info(
        "Starting Shopify Auth Backend — log_level=%s, db=%s",
        settings.log_level.upper(),
        settings.sqlite_url,
    )

    app = FastAPI(title="Shopify Auth Backend", version="0.1.0")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")

    app.middleware("http")(log_requests_middleware)
    logger.debug("Request-logging middleware registered.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_model=None)
    async def root(request: Request, db: Session = Depends(get_db)) -> Response:
        """Smart entry-point that handles two distinct Shopify request types:

        1. Install trigger (from App Store / install link):
           GET /?shop=xxx&hmac=xxx&timestamp=xxx  (no 'embedded' param)
           → Redirect to /auth/install to start the OAuth flow.

        2. Embedded app load (Managed Installation via Partner Dashboard):
           GET /?embedded=1&shop=xxx&id_token=xxx&host=xxx
           → Exchange id_token for offline access token (first visit only),
             then serve the app UI.
        """
        params   = dict(request.query_params)
        shop     = params.get("shop", "")
        embedded = params.get("embedded", "0")
        hmac     = params.get("hmac", "")

        # ── Case 1: New install trigger from Shopify ────────────────────────────
        # Shopify docs: When a user installs the app, Shopify sends a GET
        # request to the App URL with shop + hmac + timestamp. We detect this
        # by the presence of hmac and the absence of embedded=1.
        if shop and hmac and embedded != "1":
            logger.info("root — install trigger detected for shop=%s, redirecting to OAuth", shop)
            return RedirectResponse(
                url=f"/auth/install?shop={shop}",
                status_code=302,
            )

        # ── Case 2: Embedded app load (Managed Installation) ─────────────────────
        # Shopify sends id_token on EVERY load. Exchange it for an offline
        # access token on the FIRST visit (when DB has no token for this shop).
        logger.debug("root — embedded app load for shop=%s", shop)
        host     = params.get("host", "")
        id_token = params.get("id_token", "")
        api_key  = settings.shopify_api_key

        if shop and id_token:
            repo = ShopInstallationRepository(db)
            existing = repo.get_by_shop(shop)
            if not existing:
                # First visit — no token in DB yet. Exchange now.
                logger.info("root — no token found for shop=%s, triggering token exchange", shop)
                try:
                    await shopify_auth_service.exchange_token(
                        id_token=id_token, shop=shop, db=db
                    )
                except Exception as exc:
                    logger.error("root — token exchange failed for shop=%s: %s", shop, exc)
            else:
                logger.debug("root — token already in DB for shop=%s, skipping exchange", shop)
        shop_line = f"<p><strong>Store:</strong> {shop}</p>" if shop else ""
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Shopify App — Coming Soon</title>

                <!-- Shopify App Bridge: sends the 'ready' signal so Admin stops spinning -->
                <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
                        crossorigin="anonymous"></script>

                <style>
                    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont,
                            'Segoe UI', Roboto, sans-serif;
                            display: flex; align-items: center; justify-content: center;
                            min-height: 100vh; background: #f6f6f7; }}
                    .card {{ background: #fff; border-radius: 12px;
                             box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                             padding: 2.5rem 3rem; text-align: center;
                             max-width: 420px; }}
                    h1 {{ color: #008060; margin-bottom: .5rem; }}
                    p  {{ color: #555; }}
                    .badge {{ display: inline-block; background: #e3f5ed;
                              color: #008060; border-radius: 20px;
                              padding: .3rem 1rem; font-size: .85rem;
                              margin-top: 1rem; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>&#127881; App Running</h1>
                    <p>Backend is running successfully.</p>
                    {shop_line}
                    <div class="badge">&#9989; Frontend coming soon</div>
                </div>

                <script>
                    // Initialize App Bridge — stops the Shopify Admin loading spinner.
                    (function () {{
                        try {{
                            const apiKey = "{api_key}";
                            const host   = "{host}";
                            if (!host) {{
                                console.warn("[AppBridge] No host param — skipping init");
                                return;
                            }}
                            const app = shopify.createApp({{ apiKey, host }});
                            console.log("[AppBridge] Initialized for shop: {shop}");
                        }} catch (err) {{
                            console.error("[AppBridge] Init error:", err);
                        }}
                    }})();
                </script>
            </body>
            </html>
            """,
            status_code=200,
        )

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    logger.info("Auth router mounted at /auth.")
    return app


app = create_app()
