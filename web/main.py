"""
Production Manager — Web Interface (FastAPI).
Запуск: python -m uvicorn web.main:app --reload --port 8000
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from src.database import get_session, engine
from src.models import Base
from src.config import config
from web.routes import auth, dashboard, analytics, projects, pipeline, scan, devices, sn_pool, admin

# Создаём таблицы если их нет
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Production Manager Web",
    description="Веб-интерфейс системы управления производством",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key="production-manager-secret-key-2024-change-in-production",
    max_age=3600 * 24,  # 24 часа
)

# Статические файлы
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# Шаблоны Jinja2
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

# =============================================
# Роуты страниц (HTML)
# =============================================

app.include_router(auth.router, prefix="", tags=["Pages"])
app.include_router(dashboard.router, prefix="", tags=["Pages"])
app.include_router(analytics.router, prefix="", tags=["Pages"])
app.include_router(projects.router, prefix="", tags=["Pages"])
app.include_router(pipeline.router, prefix="", tags=["Pages"])
app.include_router(scan.router, prefix="", tags=["Pages"])
app.include_router(devices.router, prefix="", tags=["Pages"])
app.include_router(sn_pool.router, prefix="", tags=["Pages"])
app.include_router(admin.router, prefix="", tags=["Pages"])

# =============================================
# API эндпоинты (JSON)
# =============================================

from web.api import dashboard_api, analytics_api, projects_api, pipeline_api, devices_api, sn_pool_api, admin_api

app.include_router(dashboard_api.router, prefix="/api/dashboard", tags=["API Dashboard"])
app.include_router(analytics_api.router, prefix="/api/analytics", tags=["API Analytics"])
app.include_router(projects_api.router, prefix="/api/projects", tags=["API Projects"])
app.include_router(pipeline_api.router, prefix="/api/pipeline", tags=["API Pipeline"])
app.include_router(devices_api.router, prefix="/api/devices", tags=["API Devices"])
app.include_router(sn_pool_api.router, prefix="/api/sn-pool", tags=["API SN Pool"])
app.include_router(admin_api.router, prefix="/api/admin", tags=["API Admin"])


# =============================================
# Главная страница
# =============================================

@app.get("/")
async def index(request: Request):
    """Перенаправление на дашборд."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.main:app", host="127.0.0.1", port=8000, reload=True)
