"""HTML-роут для страницы маршрутных листов."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.database import get_db
from src.models import RouteConfig, ROUTE_PIPELINE_STAGES
from web.dependencies import get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/route-configs", response_class=HTMLResponse)
async def route_configs_page(request: Request):
    db = next(__import__('src.database', fromlist=['get_db']).get_db())
    user = await get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login")
    configs = db.query(RouteConfig).order_by(RouteConfig.is_default.desc(), RouteConfig.id).all()
    return templates.TemplateResponse("route_configs.html", {
        "request":  request,
        "user":     user,
        "configs":  configs,
        "pipeline_stages": ROUTE_PIPELINE_STAGES,
    })
