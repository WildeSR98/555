"""
Маршруты страницы SN Pool.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import SerialNumber
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/sn-pool")
async def sn_pool_page(request: Request, db: Session = Depends(get_db)):
    """Страница SN Pool."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    serial_numbers = db.query(SerialNumber).order_by(SerialNumber.created_at.desc()).limit(500).all()

    return templates.TemplateResponse("sn_pool.html", {
        "request": request,
        "user": user,
        "serial_numbers": serial_numbers,
    })
