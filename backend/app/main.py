from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import ask, deploy, relationships, semantics, sources, tables

settings = get_settings()

app = FastAPI(title="DB Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


for module in (sources, tables, relationships, semantics, deploy, ask):
    app.include_router(module.router)
