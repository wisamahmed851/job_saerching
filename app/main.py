from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.api.routes import auth, users, pages
import os

# Create all database tables based on models
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# Ensure the static directory exists so StaticFiles doesn't crash on startup
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)
os.makedirs("app/static/images", exist_ok=True)

# Mount StaticFiles middleware
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include the new HTML Pages router
app.include_router(pages.router, tags=["pages"])

# Include the JSON API routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])