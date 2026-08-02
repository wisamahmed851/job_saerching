from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.api.routes import auth, users, pages, companies, excel, resumes
from app.api.routes import companies_pages
from app.services.resume_service import ensure_upload_dirs
import os
import app.models

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS
origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)
os.makedirs("app/static/images", exist_ok=True)
ensure_upload_dirs()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(excel.router, prefix="/applications", tags=["excel"])
app.include_router(resumes.router, tags=["resumes"])
app.include_router(companies_pages.router, tags=["companies-pages"])
app.include_router(pages.router, tags=["pages"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])

from fastapi.routing import APIRoute