from pathlib import Path

from fastapi import HTTPException, status

from app.services.model_runtime import ModelRuntime


_runtime: ModelRuntime | None = None


def get_model_runtime() -> ModelRuntime:
    global _runtime
    if _runtime is None:
        try:
            _runtime = ModelRuntime(Path(__file__).resolve().parents[3])
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"ML artifacts are unavailable: {error}",
            ) from error
    return _runtime
