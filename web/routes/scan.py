"""
Маршруты страницы Scan.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_session
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/scan")
async def scan_page(request: Request, db: Session = Depends(get_session)):
    """Страница Scan."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("scan.html", {
        "request": request,
        "user": user,
    })
