from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_company_or_404, get_ml_dataset
from backend.database import get_db
from backend.models import Company
from backend.schemas import CompanyOut
from backend.services.personalization import company_profile
from backend.services.ml_personalization import profiles_for_companies, profile_for_company
from ml.dataset import CompanyDataset

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db), q: str | None = None,
                   limit: int = Query(100, ge=1, le=500),
                   dataset: CompanyDataset | None = Depends(get_ml_dataset)):
    if dataset is not None:
        return profiles_for_companies(dataset, query=q, limit=limit)
    stmt = select(Company).order_by(Company.id).limit(limit)
    if q:
        stmt = select(Company).where(Company.id.ilike(f"%{q}%")).order_by(Company.id).limit(limit)
    return [company_profile(company) for company in db.scalars(stmt).all()]


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, role: str = Query("ceo", pattern="^(ceo|cfo)$"),
                db: Session = Depends(get_db),
                dataset: CompanyDataset | None = Depends(get_ml_dataset)):
    if dataset is not None:
        try:
            return profile_for_company(dataset, company_id, role)
        except KeyError as exc:
            raise HTTPException(404, detail={"code": "company_not_found", "message": "Компания не найдена"}) from exc
        except ValueError as exc:
            raise HTTPException(409, detail={"code": "ambiguous_company_id", "message": "ID компании неоднозначен в исходных данных"}) from exc
    return company_profile(get_company_or_404(db, company_id), role)
