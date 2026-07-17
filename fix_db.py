from sqlalchemy import text
from app.db.session import engine

def main():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;"))
            conn.commit()
            print("Successfully updated database schema!")
    except Exception as e:
        print(f"Error updating schema: {e}")

if __name__ == "__main__":
    main()
