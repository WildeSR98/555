"""
Маршруты страницы Пул серийных номеров.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from web.routes.auth import get_current_user
from web.dependencies import render_template
from fastapi_csrf_protect import CsrfProtect
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

@router.get("/sn-pool")
def sn_pool_page(request: Request, db: Session = Depends(get_db), csrf_protect: CsrfProtect = Depends()):
    """Страница пула SN."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    return render_template("sn_pool.html", {
        "user": user,
    }, request, csrf_protect)
