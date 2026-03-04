import asyncio
import hashlib
import hmac
import json

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
import base64

from app.config.settings import settings
from app.database.engine import get_db
from app.database.repositories.shop_installation_repository import ShopInstallationRepository
from app.utils.logger import get_logger
from app.utils.retry import retry_async
from app.services.ai_service import ai_service

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Signature Verification Helper
# ─────────────────────────────────────────────────────────────

def verify_wa_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """
    Verify the x-wa-signature HMAC-SHA256 sent by the WhatsApp Platform.
    The HMAC is computed over the raw request body using the shared secret.
    """
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    # Use compare_digest to prevent timing attacks
    return hmac.compare_digest(expected, signature)

async def send_product_messages(api_key: str, phone_number: str, products: list):
    """
    Background task to send up to 3 separate API calls for each product.
    Resolves the image to a base64 string and formats the text per product.
    """
    if not products or not api_key:
        logger.warning("send_product_messages — skipped: no products or api_key missing")
        return

    to_send = products[:3]
    logger.info("━" * 60)
    logger.info(f"📤 PRODUCT DISPATCH — sending {len(to_send)} product(s) to {phone_number}")
    logger.info("━" * 60)

    sent_ok = 0
    send_url = f"{settings.wa_platform_url.rstrip('/')}/api/send-message"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, p in enumerate(to_send, 1):
            title     = p.get("title", "Product")
            handle    = p.get("handle", "")
            price     = p.get("price", "N/A")
            image_url = p.get("image_url")

            logger.info(f"  [{idx}/{len(to_send)}] Processing: {title!r} | handle={handle!r} | price={price}")

            # ── 1. Guard: image_url required ────────────────────────────────
            if not image_url:
                logger.warning(f"  [{idx}/{len(to_send)}] ⚠️  Skipped — no image_url for product: {title!r}")
                continue

            # ── 2. Download image → retry up to 2x on transient network errors ──
            try:
                img_res = await retry_async(
                    lambda: client.get(image_url),
                    retries=2,
                    delay=1.0,
                    exceptions=(httpx.RequestError, httpx.TimeoutException),
                    label=f"image-download [{title!r}]",
                )
                img_res.raise_for_status()
                b64_data  = base64.b64encode(img_res.content).decode("utf-8")
                # Detect MIME type from response headers (e.g. "image/jpeg", "image/png")
                mime_type = img_res.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                ext       = mime_type.split("/")[-1]   # "jpeg", "png", "webp", etc.
                filename  = f"{handle}.{ext}" if handle else f"product.{ext}"
                logger.info(
                    f"  [{idx}/{len(to_send)}] 🖼️  Image downloaded — "
                    f"status={img_res.status_code} mime={mime_type} size={len(img_res.content):,} bytes"
                )
            except Exception as e:
                logger.error(
                    f"  [{idx}/{len(to_send)}] ❌ Image download FAILED for {title!r} "
                    f"| url={image_url} | error={e}"
                )
                continue

            # ── 3. Build payload ─────────────────────────────────────────────
            # Per API spec: `caption` inside the media object is what renders
            # as text beneath the image in WhatsApp. Putting text in top-level
            # `content` alongside a `media` object causes the image to be sent
            # as a raw file/document instead of an inline picture.
            url     = f"https://ismailsclothing.com/products/{handle}"
            caption = f"*{title}*\n\n*PKR {price}*\n\n{url}"

            payload = {
                "phoneNumber": phone_number,
                "content": caption,     # required non-empty field by the API
                "media": {
                    "type":     mime_type,  # e.g. "image/jpeg", "image/png"
                    "data":     b64_data,
                    "filename": filename,   # e.g. "bu25116-beg.jpeg"
                    "caption":  caption,   # renders as text beneath the image in WhatsApp
                }
            }
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
            }

            # ── 4. POST to WA Platform → retry up to 3x on transient errors ──
            # Only retry on network/timeout errors. 4xx responses (bad request,
            # auth) are not retried since they won't change on a retry.
            try:
                res = await retry_async(
                    lambda: client.post(send_url, json=payload, headers=headers),
                    retries=3,
                    delay=1.0,
                    exceptions=(httpx.RequestError, httpx.TimeoutException),
                    label=f"WA send-product [{title!r}]",
                )
                res.raise_for_status()
                sent_ok += 1
                logger.info(
                    f"  [{idx}/{len(to_send)}] ✅ Sent OK — "
                    f"status={res.status_code} | product={title!r}"
                )
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"  [{idx}/{len(to_send)}] ❌ WA Platform rejected product {title!r} — "
                    f"status={e.response.status_code} | body={e.response.text[:200]}"
                )
            except Exception as e:
                logger.error(
                    f"  [{idx}/{len(to_send)}] ❌ Failed to send product {title!r} — error={e}"
                )

    logger.info("━" * 60)
    logger.info(
        f"📤 DISPATCH COMPLETE — {sent_ok}/{len(to_send)} product(s) sent successfully to {phone_number}"
    )
    logger.info("━" * 60)


async def send_text_message(api_key: str, phone_number: str, text: str):
    """
    Dispatch a quick text message via the WA Platform.
    Retries up to 3 times on transient network errors.
    """
    if not text or not api_key:
        return

    send_url = f"{settings.wa_platform_url.rstrip('/')}/api/send-message"
    payload  = {"phoneNumber": phone_number, "content": text}
    headers  = {"x-api-key": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await retry_async(
                lambda: client.post(send_url, json=payload, headers=headers),
                retries=3,
                delay=1.0,
                exceptions=(httpx.RequestError, httpx.TimeoutException),
                label="WA send-text",
            )
            res.raise_for_status()
        except Exception as e:
            logger.error(f"send_text_message — all retries exhausted: {e}")


# ─────────────────────────────────────────────────────────────
# Endpoint 0 — Provision Store (You → WA Platform)
# POST /api/whatsapp/provision
# Called by the frontend "Connect WhatsApp" button.
# ─────────────────────────────────────────────────────────────

@router.post("/provision")
async def provision_store(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the Shopify embedded frontend when the merchant clicks
    "Connect WhatsApp". Calls the WA Platform provisioning endpoint,
    then stores the returned agentId + apiKey in our DB.

    Expected body: { "shop": "mystore.myshopify.com" }
    """
    body = await request.json()
    shop_domain = body.get("shop")

    if not shop_domain:
        raise HTTPException(status_code=400, detail="Missing 'shop' field")

    repo = ShopInstallationRepository(db)
    install = repo.get_offline_by_shop(shop_domain)

    if not install:
        raise HTTPException(
            status_code=404,
            detail=f"No installation found for shop: {shop_domain}. Complete OAuth first.",
        )

    # ── Already provisioned? Return existing state ──────────
    if install.wa_agent_id:
        logger.info("provision — already provisioned for shop=%s agent=%s", shop_domain, install.wa_agent_id)
        return {
            "success": True,
            "already_provisioned": True,
            "wa_status": install.wa_status,
            "wa_agent_id": install.wa_agent_id,
        }

    # ── Build the webhookUrl the WA Platform will POST events to ──
    webhook_base_url = f"{settings.app_base_url.rstrip('/')}/api/whatsapp"

    # ── Call WA Platform provisioning ───────────────────────
    provision_url = f"{settings.wa_platform_url.rstrip('/')}/api/shopify/provision"
    payload = {
        "shopId":     str(install.id),       # Use our internal DB id as shopId
        "domain":     shop_domain,
        "shopName":   shop_domain.split(".")[0],   # Simple name from domain
        "webhookUrl": webhook_base_url,
    }

    logger.info("provision — calling WA Platform for shop=%s url=%s", shop_domain, provision_url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                provision_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-shopify-secret": settings.wa_platform_shared_secret,
                },
            )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error("provision — WA Platform returned error: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(
            status_code=502,
            detail=f"WhatsApp Platform error: {e.response.status_code}",
        )
    except httpx.RequestError as e:
        logger.error("provision — Could not reach WA Platform: %s", e)
        raise HTTPException(status_code=502, detail="Could not reach WhatsApp Platform")

    # ── Save agentId + apiKey to DB ──────────────────────────
    agent_id = data.get("data", {}).get("agentId")
    api_key  = data.get("data", {}).get("apiKey")
    status   = data.get("data", {}).get("status", "INACTIVE")

    if not agent_id or not api_key:
        logger.error("provision — WA Platform response missing agentId/apiKey: %s", data)
        raise HTTPException(status_code=502, detail="Invalid response from WhatsApp Platform")

    repo.update_wa_provisioning(
        shop_domain=shop_domain,
        wa_agent_id=agent_id,
        wa_api_key=api_key,
        wa_status=status,
    )

    logger.info("provision — ✅ success for shop=%s agent=%s status=%s", shop_domain, agent_id, status)
    return {
        "success": True,
        "already_provisioned": False,
        "wa_status": status,
        "wa_agent_id": agent_id,
        "message": "WhatsApp agent provisioned. QR code will arrive in ~1–3 minutes.",
    }


# ─────────────────────────────────────────────────────────────
# Endpoint: GET /api/whatsapp/agent-status?shop=...
# Used by the frontend to poll current WA connection state + QR.
# ─────────────────────────────────────────────────────────────

@router.get("/agent-status")
def get_agent_status(shop: str, db: Session = Depends(get_db)):
    """
    Returns the current WhatsApp agent state for a shop.
    The frontend polls this to know when to show the QR code or connected state.
    """
    repo = ShopInstallationRepository(db)
    install = repo.get_offline_by_shop(shop)

    if not install:
        raise HTTPException(status_code=404, detail="Shop not found")

    return {
        "wa_agent_id":    install.wa_agent_id,
        "wa_status":      install.wa_status or "NOT_PROVISIONED",
        "wa_phone_number": install.wa_phone_number,
        "wa_qr_code":     install.wa_qr_code,   # data URI — render as <img>
    }


# ─────────────────────────────────────────────────────────────
# Endpoint 1 — Incoming WhatsApp Message  (Platform → You)
# POST /api/whatsapp/messages
# ─────────────────────────────────────────────────────────────

@router.post("/messages")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    x_wa_signature: str = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Called by the WhatsApp Platform when a customer sends a message.
    The platform expects a reply JSON: { "content": "<reply text>" }
    Return { "content": "" } to send no reply.
    """
    raw_body = await request.body()

    # ── Signature verification ──────────────────────────────
    if settings.wa_platform_shared_secret:
        if not x_wa_signature:
            logger.warning("/messages — missing x-wa-signature header")
            raise HTTPException(status_code=401, detail="Missing signature")
        if not verify_wa_signature(raw_body, x_wa_signature, settings.wa_platform_shared_secret):
            logger.warning("/messages — invalid x-wa-signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(raw_body)

    # ── Extract fields ──────────────────────────────────────
    metadata    = payload.get("metadata", {})
    shop_id     = metadata.get("shopId")
    domain      = metadata.get("domain")
    # NOTE: apiKey is intentionally NOT read from the payload.
    # It is retrieved from the database (stored securely during provisioning).

    message           = payload.get("message", {})
    message_id        = message.get("id")        # Use for deduplication later
    from_number       = message.get("from")
    contact           = message.get("contactName")
    content           = message.get("content", "")
    processed_content = message.get("processedContent")  # WA-generated image caption
    media             = message.get("media")     # None for text-only messages

    # ── Load API key from env (settings.wa_api_key) ───────────────
    wa_api_key = settings.wa_api_key
    if not wa_api_key:
        logger.error("/messages — WA_API_KEY is not set in .env — cannot send replies")

    # Merge text content with image caption (processedContent) into a single enriched string.
    # This avoids sending the image to OpenAI's vision API — cheaper, faster, and sufficient
    # since the WA platform already describes the image for us.
    if processed_content and processed_content != content:
        if content:
            effective_text = f"{content}\n\n Fine products based on this image description \n [Image description: {processed_content}]"
        else:
            effective_text = f"Fine products based on this image description \n [Image description: {processed_content}]"  
    else:
        effective_text = content

    logger.info(f"Effective text: {effective_text}")

    media_url    = media.get("url") if media else None  # Only used for SigLIP visual embedding
    chat_history = payload.get("chatHistory", [])

    logger.info(
        "/messages — shop=%s | from=%s (%s) | msg_id=%s | content=%r | has_processed=%s | has_media=%s | history_len=%d",
        domain, from_number, contact, message_id, content,
        processed_content is not None, media is not None, len(chat_history)
    )

    # ── AI processing ─────────────────────────────────────────────────────────
    # Consistent ordering:
    #   1. on_search_start  → asyncio.create_task()      fires immediately (before response)
    #   2. return reply     → {"content": reply}          inline text reply to WA platform
    #   3. on_products_found → background_tasks.add_task  fires after response is sent
    try:
        async def _on_search_start(msg: str):
            # Fire immediately so the customer sees "Searching..." right away
            if wa_api_key and from_number:
                asyncio.create_task(send_text_message(wa_api_key, from_number, msg))

        async def _on_products_found(products: list):
            # Schedule after the inline reply is returned so product cards
            # always arrive after the text response, never before it
            if products and wa_api_key and from_number:
                background_tasks.add_task(send_product_messages, wa_api_key, from_number, products)

        reply = await ai_service.process_whatsapp_message(
            text_content=effective_text,
            media_url=media_url,
            phone_number=from_number,
            chat_history=chat_history,
            on_search_start=_on_search_start,
            on_products_found=_on_products_found,
        )

    except Exception as e:
        logger.error(f"Error calling AI service: {e}")
        reply = "I'm sorry, I'm experiencing technical difficulties right now. Please try again later."

    # Return the AI reply inline — WA platform displays this as the chat response
    return {"content": reply}


# ─────────────────────────────────────────────────────────────
# Endpoint 2 — QR Code Update  (Platform → You)
# POST /api/whatsapp/qr
# ─────────────────────────────────────────────────────────────

@router.post("/qr")
async def receive_qr(
    request: Request,
    x_wa_signature: str = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Called by the WA Platform when a new QR code is generated.
    Triggered ~1–3 min after provisioning or when the session expires.
    """
    raw_body = await request.body()

    # ── Signature verification ──────────────────────────────
    if settings.wa_platform_shared_secret:
        if not x_wa_signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        if not verify_wa_signature(raw_body, x_wa_signature, settings.wa_platform_shared_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(raw_body)

    metadata = payload.get("metadata", {})
    domain   = metadata.get("domain")
    qr_code  = payload.get("qrCode")  # Full data URI

    logger.info("/qr — shop=%s | qr_length=%d", domain, len(qr_code) if qr_code else 0)

    if domain and qr_code:
        ShopInstallationRepository(db).update_wa_qr_code(
            shop_domain=domain,
            wa_qr_code=qr_code,
        )

    return {"received": True}


# ─────────────────────────────────────────────────────────────
# Endpoint 3 — Connection Status Update  (Platform → You)
# POST /api/whatsapp/status
# ─────────────────────────────────────────────────────────────

@router.post("/status")
async def receive_status(
    request: Request,
    x_wa_signature: str = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Called by the WA Platform when the WhatsApp connection state changes.

    Events:
      - whatsapp.connecting   → Merchant scanned QR, authenticating
      - whatsapp.connected    → Session active, phoneNumber included
      - whatsapp.disconnected → Session dropped/logged out
      - whatsapp.error        → Auth failure or crash
    """
    raw_body = await request.body()

    # ── Signature verification ──────────────────────────────
    if settings.wa_platform_shared_secret:
        if not x_wa_signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        if not verify_wa_signature(raw_body, x_wa_signature, settings.wa_platform_shared_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(raw_body)

    metadata     = payload.get("metadata", {})
    domain       = metadata.get("domain")
    event        = payload.get("event")
    phone_number = payload.get("phoneNumber")  # Only on whatsapp.connected

    logger.info("/status — shop=%s | event=%s | phone=%s", domain, event, phone_number)

    # ── Map event → DB status ───────────────────────────────
    STATUS_MAP = {
        "whatsapp.connecting":   "CONNECTING",
        "whatsapp.connected":    "ACTIVE",
        "whatsapp.disconnected": "DISCONNECTED",
        "whatsapp.error":        "ERROR",
    }

    wa_status = STATUS_MAP.get(event)
    if wa_status and domain:
        ShopInstallationRepository(db).update_wa_status(
            shop_domain=domain,
            wa_status=wa_status,
            wa_phone_number=phone_number,
        )
        logger.info("/status — DB updated: shop=%s status=%s", domain, wa_status)
    else:
        logger.warning("/status — unknown event=%s for shop=%s", event, domain)

    return {"received": True}
