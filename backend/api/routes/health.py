from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        raise HTTPException(503, detail={"code": "database_unavailable", "message": "Хранилище временно недоступно"}) from exc
