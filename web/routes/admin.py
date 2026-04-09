"""
Маршруты страницы Admin.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/admin")
async def admin_page(request: Request, db: Session = Depends(get_db)):
    """Страница Admin Panel."""
    user = get_current_user(request)
    if not user or user.role != 'ADMIN':
        return RedirectResponse(url="/dashboard")

    users = db.query(User).order_by(User.date_joined.desc()).all()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "users": users,
    })
