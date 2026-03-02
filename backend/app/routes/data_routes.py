from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import io
import json
from openai import AsyncOpenAI

from app.config.settings import settings
from app.database.engine import get_db
from app.database.repositories.shop_installation_repository import ShopInstallationRepository
from app.services.shopify_service import ShopifyService
from app.services.embedding_service import embedding_service
from app.services.search_service import search_service
from app.prompts.whatsapp_prompts import SEARCH_TOOL_SCHEMA, SYSTEM_PROMPT
from app.templates import (
    DASHBOARD_HTML,
    SEARCH_VISUALIZER_HTML,
    generate_product_row,
    generate_customer_row,
    generate_order_row
)
from ingest_products import ingest_products, get_sync_status, SYNC_STATUS

router = APIRouter()

_ai_client = AsyncOpenAI(api_key=settings.openai_api_key)

# The real Isla system prompt is used — tool_choice=required enforces the tool call
# even for messages that might not normally trigger one (e.g. vague queries).

# ... existing routes ...

@router.get("/search-visualizer", response_class=HTMLResponse)
async def search_visualizer():
    return HTMLResponse(content=SEARCH_VISUALIZER_HTML)


@router.post("/api/search/visualize")
async def api_visualize_search(
    query: str = Form(""),
    limit: int = Form(10),
    color_filter: str = Form(""),
    max_price: Optional[float] = Form(None),
    min_score: Optional[float] = Form(None),
):
    """
    Backend API for the visual debugger.
    Handles text embedding and hybrid search (text-only, image search removed).
    Supports optional color_filter, max_price and min_score filters.
    """
    text_vector = None

    # 1. Text Embedding
    if query:
        text_vector = embedding_service.embed_text(query)

    # 3. Build optional filter string
    filters = []
    if color_filter:
        filters.append(f'color = "{color_filter.upper()}"')
    if max_price is not None:
        filters.append(f"price <= {max_price}")
    filter_str = " AND ".join(filters) if filters else None

    # 3. Hybrid Search
    results = search_service.perform_hybrid_search(
        query=query,
        text_vector=text_vector,
        limit=limit,
        filter_str=filter_str,
        ranking_score_threshold=min_score if min_score and min_score > 0 else None,
    )

    return {"results": results, "filter_applied": filter_str}


@router.post("/api/search/ai-visualize")
async def api_ai_visualize_search(request: Request):
    """
    AI-layer search endpoint.
    Forces the LLM to always call search_products (tool_choice=required),
    then runs the hybrid search pipeline with the AI-extracted parameters.
    Returns both the AI extraction metadata and the final search results.
    """
    body      = await request.json()
    query     = body.get("query", "").strip()
    limit     = int(body.get("limit", 6))
    min_score = body.get("min_score", None)  # Optional ranking score threshold

    if not query:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    # ── Step 1: Force LLM tool call ─────────────────────────────────────────
    try:
        ai_response = await _ai_client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": query},
            ],
            tools=[SEARCH_TOOL_SCHEMA],
            tool_choice={"type": "function", "function": {"name": "search_products"}},
            max_tokens=300,
            temperature=0,
        )
        tool_call = ai_response.choices[0].message.tool_calls[0]
        ai_args   = json.loads(tool_call.function.arguments)
        usage     = ai_response.usage
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"AI extraction failed: {e}"})

    search_query  = ai_args.get("search_query",      query)
    color_filter  = ai_args.get("color_filter",       None)
    max_price     = ai_args.get("max_price",           None)
    search_msg    = ai_args.get("searching_message",  "Searching…")

    # ── Step 2: Build filter and embed ──────────────────────────────────────
    filters = []
    if color_filter:
        filters.append(f'color = "{color_filter.upper()}"')
    if max_price is not None:
        filters.append(f"price <= {max_price}")
    filter_str = " AND ".join(filters) if filters else None

    try:
        text_vector = embedding_service.embed_text(search_query)
    except Exception:
        text_vector = None

    # ── Step 3: Hybrid search ────────────────────────────────────────────────
    try:
        results = search_service.perform_hybrid_search(
            query=search_query,
            text_vector=text_vector,
            limit=limit,
            filter_str=filter_str,
            ranking_score_threshold=min_score if min_score and min_score > 0 else None,
        )
    except Exception as e:
        results = []

    return {
        "ai_extraction": {
            "search_query":      search_query,
            "color_filter":      color_filter,
            "max_price":         max_price,
            "min_score":         min_score,
            "searching_message": search_msg,
            "filter_str":        filter_str,
            "model":             settings.chat_model,
            "prompt_tokens":     usage.prompt_tokens     if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
        },
        "results": results,
    }

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(shop: str, db: Session = Depends(get_db)):
    # 1. Get Token from DB
    repo = ShopInstallationRepository(db)
    installation = repo.get_by_shop(shop)
    
    if not installation:
        return HTMLResponse(content=f"<h1>Error: No installation found for shop: {shop}</h1>", status_code=404)
    
    # We take the first active installation (usually there is only one per shop)
    install = installation[0]
    token = install.access_token

    # 2. Call Shopify API using Service
    service = ShopifyService(shop_domain=shop, access_token=token)
    
    try:
        products = await service.get_products(limit=5)
        customers = await service.get_customers(limit=5)
        orders = await service.get_orders(limit=5)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error calling Shopify API: {str(e)}</h1>", status_code=500)

    # 3. Render HTML
    products_html = "".join([generate_product_row(p) for p in products]) or "<div class='text-gray-400 italic p-4'>No products found.</div>"
    customers_html = "".join([generate_customer_row(c) for c in customers]) or "<div class='text-gray-400 italic p-4'>No customers found.</div>"
    orders_html = "".join([generate_order_row(o) for o in orders]) or "<tr><td colspan='5' class='text-center py-4 text-gray-400 italic'>No orders found.</td></tr>"

    html_content = DASHBOARD_HTML.format(
        shop_domain=shop,
        masked_token=token[-4:] if token else "....",
        product_count=len(products),
        customer_count=len(customers),
        order_count=len(orders),
        products_html=products_html,
        customers_html=customers_html,
        orders_html=orders_html
    )

    return HTMLResponse(content=html_content)


# ── Product Sync Endpoints ─────────────────────────────────────────────────────

@router.post("/api/products/sync")
async def sync_products(background_tasks: BackgroundTasks, shop: str, db: Session = Depends(get_db)):
    """
    Trigger background ingestion of all products for a shop into Meilisearch.
    Returns immediately with 202 Accepted.
    """
    repo = ShopInstallationRepository(db)
    installation = repo.get_by_shop(shop)
    if not installation:
        raise HTTPException(status_code=404, detail=f"Shop not found: {shop}")

    # Prevent double-trigger if already processing
    current = get_sync_status(shop)
    if current.get("status") in ("fetching", "processing"):
        return JSONResponse(
            status_code=409,
            content={"detail": "Sync already in progress.", "status": current}
        )

    # Clear old status and kick off background task
    SYNC_STATUS[shop] = {"status": "fetching", "total": 0, "done": 0, "error": ""}
    background_tasks.add_task(ingest_products, shop_domain=shop)

    return JSONResponse(status_code=202, content={"detail": "Product sync started.", "shop": shop})


@router.get("/api/products/sync-status")
async def sync_status(shop: str):
    """
    Poll the current sync status for a shop.
    Returns: { status, total, done, error }
    """
    return JSONResponse(content=get_sync_status(shop))

