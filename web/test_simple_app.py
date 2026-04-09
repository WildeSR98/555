"""
Минимальный тест FastAPI приложения.
"""

import sys
sys.path.insert(0, '.')

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="test-secret-key",
)

@app.get("/test-login")
async def test_login(request: Request):
    """Тестовая страница входа."""
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.get("/test-simple")
async def test_simple():
    """Простая страница без шаблонов."""
    return HTMLResponse("<h1>Simple test OK</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
