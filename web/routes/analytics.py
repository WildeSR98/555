"""
Маршруты страницы Analytics.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from src.database import get_db
from src.models import Device, WorkLog, User
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/analytics")
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    """Страница Analytics."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    employees = db.query(User).filter(User.is_active == True).all()

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "user": user,
        "employees": employees
    })
