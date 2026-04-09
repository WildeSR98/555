"""
Маршруты страницы Devices.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Device
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/devices")
async def devices_page(request: Request, db: Session = Depends(get_db)):
    """Страница Devices."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    devices = db.query(Device).order_by(Device.created_at.desc()).limit(500).all()

    return templates.TemplateResponse("devices.html", {
        "request": request,
        "user": user,
        "devices": devices,
    })
