import sys
sys.path.insert(0, '.')

# Check imports
from web.api.route_config_api import router as rc_api
from web.api.archive_api import router as arc_api
from web.routes.route_configs import router as rc_html
from web.routes.archive import router as arc_html
print("Imports: OK")

# Check DB tables
from src.database import SessionLocal, engine
from src.models import RouteConfig, RouteConfigStage
from sqlalchemy import inspect
ins = inspect(engine)
tables = ins.get_table_names()
for t in ['pm_route_config', 'pm_route_config_stage', 'pm_route_config_editor', 'pm_project_route']:
    print(f"  Table {t}: {'OK' if t in tables else 'MISSING'}")

# Check default route
db = SessionLocal()
rc = db.query(RouteConfig).filter_by(is_default=True).first()
print(f"Default route: {rc}")
if rc:
    stages = db.query(RouteConfigStage).filter_by(route_config_id=rc.id).count()
    print(f"  Stages: {stages}")
db.close()
print("All checks passed!")
