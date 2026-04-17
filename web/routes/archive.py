"""HTML-роут для страницы архива проектов."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from web.dependencies import get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/archive", response_class=HTMLResponse)
async def archive_page(request: Request):
    db = next(__import__('src.database', fromlist=['get_db']).get_db())
    user = await get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("archive.html", {
        "request": request,
        "user":    user,
    })
