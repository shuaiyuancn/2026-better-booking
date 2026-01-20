from main import db
from sqlalchemy import text

try:
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE task ADD COLUMN target_time_start TEXT"))
        conn.commit()
    print("Migration successful: Added target_time_start to task table.")
except Exception as e:
    print(f"Migration failed: {e}")
