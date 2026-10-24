from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_company_or_404
from backend.database import get_db
from backend.models import Company
from backend.schemas import CompanyOut
from backend.services.personalization import company_profile

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db), q: str | None = None,
                   limit: int = Query(100, ge=1, le=500)):
    stmt = select(Company).order_by(Company.id).limit(limit)
    if q:
        stmt = select(Company).where(Company.id.ilike(f"%{q}%")).order_by(Company.id).limit(limit)
    return [company_profile(company) for company in db.scalars(stmt).all()]


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, role: str = Query("ceo", pattern="^(ceo|cfo)$"),
                db: Session = Depends(get_db)):
    return company_profile(get_company_or_404(db, company_id), role)
