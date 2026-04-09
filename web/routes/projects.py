"""
Маршруты страницы Projects.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Project, Device
from web.routes.auth import get_current_user
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@router.get("/projects")
async def projects_page(request: Request, db: Session = Depends(get_db)):
    """Страница Projects."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    projects = db.query(Project).order_by(Project.created_at.desc()).all()

    return templates.TemplateResponse("projects.html", {
        "request": request,
        "user": user,
        "projects": projects,
    })
