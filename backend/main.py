from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Medquest Proof Corrector API",
    description="API for the AI-assisted exam grading platform",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Medquest Corrector API is running"}

# TODO: Include routers here
# from app.api.v1 import exams, uploads
# app.include_router(exams.router, prefix="/api/v1/exams", tags=["Exams"])
