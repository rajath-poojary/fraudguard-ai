from pathlib import Path

from fastapi import HTTPException, status

from app.services.model_runtime import ModelRuntime


_runtime: ModelRuntime | None = None


def get_model_runtime() -> ModelRuntime:
    global _runtime
    if _runtime is None:
        try:
            module_path = Path(__file__).resolve()
            roots = [module_path.parents[3], module_path.parents[2]]
            root = next((candidate for candidate in roots if (candidate / "ml" / "models").is_dir()), roots[0])
            _runtime = ModelRuntime(root)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"ML artifacts are unavailable: {error}",
            ) from error
    return _runtime
