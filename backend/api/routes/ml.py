from fastapi import APIRouter, HTTPException

from backend.services.ml_quality import get_ml_quality_report

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/quality")
def get_ml_quality():
    """Return CSV diagnostics, ML contract validation, and the labeled regression benchmark."""
    try:
        return get_ml_quality_report()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ml_dataset_unavailable",
                "message": "Не удалось построить отчёт: проверьте путь к CSV компаний.",
            },
        ) from exc
