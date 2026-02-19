from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.engine import get_db
from app.database.repositories.shop_installation_repository import ShopInstallationRepository
from app.services.shopify_service import ShopifyService
from app.templates import DASHBOARD_HTML, generate_product_row, generate_customer_row, generate_order_row

router = APIRouter()

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
