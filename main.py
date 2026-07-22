"""YKS Tercih Tahmin API - FastAPI uygulama giriş noktası."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Comment, Department
from predictor import calculate_2026_forecast, calculate_winning_chance
from schemas import (
    CalculateListRequest,
    CommentCreate,
    CommentOut,
    DepartmentChanceOut,
    DepartmentDetailOut,
    DepartmentForecastOut,
    DepartmentOut,
    StatsOut,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Uygulama ayağa kalkarken veritabanı tablolarının var olduğundan emin olur."""
    init_db()
    yield


app = FastAPI(title="YKS Tercih Tahmin API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def read_index(request: Request) -> HTMLResponse:
    """Tek sayfalık frontend arayüzünü (templates/index.html) sunar."""
    return templates.TemplateResponse(request, "index.html")


def _to_forecast_out(department: Department) -> DepartmentForecastOut:
    """Bir Department kaydını 2026 tahmin bilgileriyle birlikte response modeline dönüştürür."""
    forecast = calculate_2026_forecast(
        rank_2023=department.rank_2023,
        rank_2024=department.rank_2024,
        rank_2025=department.rank_2025,
        user_demand_count=department.user_demand_count,
    )
    base = DepartmentOut.model_validate(department)
    return DepartmentForecastOut(
        **base.model_dump(),
        forecast_min_rank=forecast.forecast_min_rank,
        forecast_max_rank=forecast.forecast_max_rank,
        trend_status=forecast.trend_status,
    )


def _get_department_or_404(department_id: int, db: Session) -> Department:
    """Bölümü ID ile getirir, bulunamazsa 404 hatası fırlatır."""
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail=f"'{department_id}' ID'li bölüm bulunamadı.")
    return department


@app.get("/api/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    """Ana sayfa istatistik sayaçları için toplam bölüm/üniversite/şehir sayısını döndürür."""
    return StatsOut(
        total_departments=db.query(Department).count(),
        total_universities=db.query(Department.university_name).distinct().count(),
        total_cities=db.query(Department.city).distinct().count(),
    )


@app.get("/api/departments", response_model=list[DepartmentForecastOut])
def search_departments(
    query: str | None = Query(default=None, description="Üniversite, bölüm veya şehir adında arama"),
    city: str | None = Query(default=None, description="Şehre göre filtrele"),
    score_type: str | None = Query(default=None, description="Puan türüne göre filtrele (SAY, EA, SÖZ, DİL)"),
    near_rank: int | None = Query(
        default=None, gt=0, description="Verilirse sonuçlar bu sıralamaya en yakın bölüm önce gelecek şekilde sıralanır"
    ),
    limit: int = Query(default=50, le=200, gt=0),
    db: Session = Depends(get_db),
) -> list[DepartmentForecastOut]:
    """Bölümleri arar/filtreler ve her biri için 2026 tahmin bandını ekler."""
    stmt = select(Department)

    if query:
        like_pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Department.university_name.ilike(like_pattern),
                Department.department_name.ilike(like_pattern),
                Department.city.ilike(like_pattern),
            )
        )
    if city:
        stmt = stmt.where(Department.city.ilike(f"%{city}%"))
    if score_type:
        stmt = stmt.where(Department.score_type == score_type)

    if near_rank is not None:
        stmt = stmt.order_by(func.abs(Department.rank_2025 - near_rank))

    stmt = stmt.limit(limit)
    departments = db.scalars(stmt).all()

    return [_to_forecast_out(department) for department in departments]


@app.get("/api/departments/{dept_id}", response_model=DepartmentDetailOut)
def get_department_detail(dept_id: int, db: Session = Depends(get_db)) -> DepartmentDetailOut:
    """Bir bölümün tam detayını, 2026 tahminini ve yorumlarını (en yeniden en eskiye) döndürür."""
    department = _get_department_or_404(dept_id, db)

    comments = (
        db.query(Comment)
        .filter(Comment.department_id == dept_id)
        .order_by(Comment.created_at.desc())
        .all()
    )

    forecast_out = _to_forecast_out(department)
    return DepartmentDetailOut(
        **forecast_out.model_dump(),
        comments=[CommentOut.model_validate(comment) for comment in comments],
    )


@app.post("/api/departments/{dept_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(dept_id: int, payload: CommentCreate, db: Session = Depends(get_db)) -> CommentOut:
    """Bir bölüme yeni yorum ekler."""
    _get_department_or_404(dept_id, db)

    comment = Comment(department_id=dept_id, nickname=payload.nickname, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentOut.model_validate(comment)


@app.post("/api/calculate-list", response_model=list[DepartmentChanceOut])
def calculate_list(payload: CalculateListRequest, db: Session = Depends(get_db)) -> list[DepartmentChanceOut]:
    """Öğrencinin tercih listesindeki her bölüm için kazanma ihtimalini hesaplar.

    Her istenen bölümün `user_demand_count` alanı bir artırılır ve sonuçlar
    öğrencinin gönderdiği tercih sırası korunarak döndürülür.
    """
    results: list[DepartmentChanceOut] = []

    for department_id in payload.department_ids:
        department = _get_department_or_404(department_id, db)

        department.user_demand_count += 1

        forecast = calculate_2026_forecast(
            rank_2023=department.rank_2023,
            rank_2024=department.rank_2024,
            rank_2025=department.rank_2025,
            user_demand_count=department.user_demand_count,
        )
        chance = calculate_winning_chance(
            user_rank=payload.user_rank,
            forecast_min_rank=forecast.forecast_min_rank,
            forecast_max_rank=forecast.forecast_max_rank,
        )

        results.append(
            DepartmentChanceOut(
                department_id=department.id,
                university_name=department.university_name,
                department_name=department.department_name,
                forecast_min_rank=forecast.forecast_min_rank,
                forecast_max_rank=forecast.forecast_max_rank,
                trend_status=forecast.trend_status,
                chance_message=chance.message,
                chance_color=chance.color,
            )
        )

    db.commit()
    return results


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
