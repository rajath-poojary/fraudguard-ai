from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin, auth, behavior, dashboard, network, prediction, temporal, transactions

app = FastAPI(
	title="FraudGuard API",
	version="1.0.0",
	description="Transaction fraud analysis and risk decisions.",
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(behavior.router)
app.include_router(temporal.router)
app.include_router(prediction.router)
app.include_router(network.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
	return {"status": "ok"}
