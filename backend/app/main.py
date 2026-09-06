from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.v1 import admin, analytics, auth, behavior, dashboard, events, feedback, investigations, models, network, prediction, temporal, transactions
from app.core.config import settings

app = FastAPI(
	title="FraudGuard API",
	version="1.0.0",
	description="Transaction fraud analysis and risk decisions.",
)

# CORS configuration from environment
allowed_origins = os.getenv(
	"ALLOWED_ORIGINS",
	"http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
	CORSMiddleware,
	allow_origins=[origin.strip() for origin in allowed_origins],
	allow_credentials=True,
	allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
	allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(behavior.router)
app.include_router(temporal.router)
app.include_router(prediction.router)
app.include_router(network.router)
app.include_router(investigations.router)
app.include_router(feedback.router)
app.include_router(models.router)
app.include_router(analytics.router)
app.include_router(events.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
	return {"status": "ok"}
