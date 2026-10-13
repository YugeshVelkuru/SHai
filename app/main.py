from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db.session import init_db
from app.services.seed_data import seed_database

settings = get_settings()
CHAT_PAGE = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_database()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Enterprise conversational AI backend with Dialogflow CX webhooks, "
        "RAG-powered knowledge retrieval, ticket tracking, and analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["SmartAssist"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root():
    return FileResponse(CHAT_PAGE)
