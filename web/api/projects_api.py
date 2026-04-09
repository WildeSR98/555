"""
API эндпоинты для Projects.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Project, Device, Operation, SerialNumber

router = APIRouter()


@router.get("/")
async def get_projects(db: Session = Depends(get_db)):
    """Получить все проекты."""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "spec_link": p.spec_link,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "device_count": db.query(Device).filter(Device.project_id == p.id).count(),
        }
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Получить конкретный проект."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "Project not found"}
    
    devices = db.query(Device).filter(Device.project_id == project_id).all()
    
    return {
        "id": project.id,
        "code": project.code,
        "name": project.name,
        "description": project.description,
        "spec_link": project.spec_link,
        "devices": [
            {
                "id": d.id,
                "sn": d.serial_number,
                "status": d.status,
                "model": d.name,
            }
            for d in devices
        ],
    }
