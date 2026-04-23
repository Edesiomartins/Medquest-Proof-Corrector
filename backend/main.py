from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Medquest Proof Corrector API",
    description="API for the AI-assisted exam grading platform",
    version="1.0.0",
)

_origins = settings.cors_origin_list()
_allow_cred = "*" not in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_cred,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Medquest Corrector API is running"}

from app.api.v1 import exams, uploads, classes

app.include_router(exams.router, prefix="/api/v1/exams", tags=["Exams"])
app.include_router(uploads.router, prefix="/api/v1/batches", tags=["Uploads"])
app.include_router(classes.router, prefix="/api/v1")
