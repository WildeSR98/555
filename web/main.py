"""
Production Manager — Web Interface (FastAPI).
Запуск: python -m uvicorn web.main:app --reload --port 8000
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Добавляем корень проекта в PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.logger import logger
import time

from src.database import get_session, engine
from src.models import Base, RouteConfig, RouteConfigStage, ROUTE_PIPELINE_STAGES
from src.config import config
from web.routes import auth, dashboard, analytics, projects, pipeline, scan, devices, sn_pool, admin
from web.routes import route_configs as route_configs_router
from web.routes import archive as archive_router
from web.dependencies import get_current_user, require_admin, require_manager
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError

# Создаём таблицы если их нет
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    _init_default_route()
    yield
    # Shutdown
    logger.info("Application shutting down...")


def _init_default_route():
    """Create the default RouteConfig (all stages enabled) if it doesn't exist yet."""
    from src.database import SessionLocal
    db = SessionLocal()
    try:
        exists = db.query(RouteConfig).filter_by(is_default=True).first()
        if not exists:
            from datetime import datetime
            rc = RouteConfig(
                name='Стандартный маршрут (все этапы)',
                description='Дефолтная конфигурация — все 11 этапов включены.',
                is_default=True,
                created_at=datetime.now(),
            )
            db.add(rc)
            db.flush()
            for key, label, idx in ROUTE_PIPELINE_STAGES:
                db.add(RouteConfigStage(
                    route_config_id=rc.id,
                    stage_key=key,
                    order_index=idx,
                    is_enabled=True,
                ))
            db.commit()
            logger.info(f"Default RouteConfig created: id={rc.id}")
    except Exception as e:
        logger.warning(f"Could not init default route: {e}")
    finally:
        db.close()

app = FastAPI(
    title="Production Manager Web",
    description="Веб-интерфейс системы управления производством",
    version="1.0.0",
    lifespan=lifespan,
)

# CSRF Configuration
class CsrfSettings(BaseModel):
    secret_key: str = config.csrf_secret
    cookie_key: str = "fastapi-csrf-token"
    token_key: str = "token_key"
    cookie_samesite: str = "lax"
    token_location: str = "body"  # Важно! Токен в теле формы, а не в заголовке

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

@app.exception_handler(CsrfProtectError)
async def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
    # Для API возвращаем JSON
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
    
    # Для HTML-страниц возвращаем форму с ошибкой
    if request.url.path == "/login":
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
        response = templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"Ошибка CSRF-защиты: {exc.message}",
        })
        return response
    
    # Для остальных страниц - JSON
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"Status: {response.status_code} | Duration: {duration:.4f}s"
    )
    return response


# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key,
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
app.include_router(route_configs_router.router, prefix="", tags=["Pages"])
app.include_router(archive_router.router, prefix="", tags=["Pages"])

# =============================================
# API эндпоинты (JSON)
# =============================================

from web.api import dashboard_api, analytics_api, projects_api, pipeline_api, devices_api, sn_pool_api, admin_api, scan_api, health_api
from web.api import route_config_api, archive_api

app.include_router(dashboard_api.router,    prefix="/api/dashboard",      tags=["API Dashboard"],  dependencies=[Depends(get_current_user)])
app.include_router(health_api.router,       prefix="/api/health",          tags=["System Health"])
app.include_router(analytics_api.router,    prefix="/api/analytics",       tags=["API Analytics"],  dependencies=[Depends(get_current_user)])
app.include_router(projects_api.router,     prefix="/api/projects",        tags=["API Projects"],   dependencies=[Depends(get_current_user)])
app.include_router(pipeline_api.router,     prefix="/api/pipeline",        tags=["API Pipeline"],   dependencies=[Depends(get_current_user)])
app.include_router(devices_api.router,      prefix="/api/devices",         tags=["API Devices"],    dependencies=[Depends(get_current_user)])
app.include_router(sn_pool_api.router,      prefix="/api/sn-pool",         tags=["API SN Pool"],    dependencies=[Depends(get_current_user)])
app.include_router(admin_api.router,        prefix="/api/admin",           tags=["API Admin"],      dependencies=[Depends(require_admin)])
app.include_router(scan_api.router,         prefix="/api/scan",            tags=["API Scan"],       dependencies=[Depends(get_current_user)])
app.include_router(route_config_api.router, prefix="/api/route-configs",   tags=["API Routes"],     dependencies=[Depends(get_current_user)])
app.include_router(archive_api.router,      prefix="/api/archive",         tags=["API Archive"],    dependencies=[Depends(get_current_user)])


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
