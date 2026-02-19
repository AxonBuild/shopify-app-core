from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.controllers.auth_controller import AuthController
from app.database.engine import get_db
from app.schemas.auth_schemas import ShopInstallationsResponse

router = APIRouter()
controller = AuthController()


@router.get("/install")
async def install(shop: str, access_mode: str = "offline") -> RedirectResponse:
    return await controller.install(shop=shop, access_mode=access_mode)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    query_params = {k: v for k, v in request.query_params.items()}
    return await controller.callback(query_params=query_params, db=db)


@router.get("/shops/{shop}", response_model=ShopInstallationsResponse)
async def get_shop_connection(shop: str, db: Session = Depends(get_db)) -> ShopInstallationsResponse:
    return await controller.get_shop_connection(shop=shop, db=db)
