from src.database import SessionLocal
from src.models import RouteConfigStage
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='pm_route_config_stage' AND column_name='timer_seconds'")).fetchall()
print('DB column exists:', res)
st = db.query(RouteConfigStage).first()
if st:
    print('timer_seconds value:', st.timer_seconds)
else:
    print('No stages in DB')
db.close()
