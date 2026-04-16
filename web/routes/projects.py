"""
Маршруты страницы Projects.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Project, DeviceModel, User
from web.routes.auth import get_current_user
from web.dependencies import render_template
from fastapi_csrf_protect import CsrfProtect
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/projects")
def projects_page(request: Request, db: Session = Depends(get_db), csrf_protect: CsrfProtect = Depends()):
    """Страница Projects."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Получаем списки для фильтров и модалок
    managers = db.query(User).filter(User.is_active == True).all()
    device_models = db.query(DeviceModel).order_by(DeviceModel.category, DeviceModel.name).all()
    
    status_choices = Project.STATUS_DISPLAY

    return render_template("projects.html", {
        "user": user,
        "managers": managers,
        "device_models": device_models,
        "status_choices": status_choices,
    }, request, csrf_protect)
