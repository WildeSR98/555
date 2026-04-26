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
from web.dependencies import render_template
from fastapi_csrf_protect import CsrfProtect
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/admin")
def admin_page(request: Request, db: Session = Depends(get_db), csrf_protect: CsrfProtect = Depends()):
    """Страница Admin Panel."""
    user = get_current_user(request)
    if not user or user.role not in ('ADMIN', 'ROOT', 'SHOP_MANAGER'):
        return RedirectResponse(url="/dashboard")

    users = db.query(User).filter(User.role != 'ROOT').order_by(User.date_joined.desc()).all()

    return render_template("admin.html", {
        "user": user,
        "users": users,
    }, request, csrf_protect)
