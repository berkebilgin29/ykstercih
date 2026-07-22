"""API giriş/çıkış şemaları için Pydantic modelleri."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentOut(BaseModel):
    """Bir bölümün veritabanındaki ham bilgilerini temsil eder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    university_name: str
    faculty_name: str
    department_name: str
    score_type: str
    education_type: str
    city: str
    quota_2025: int
    rank_2023: int
    rank_2024: int
    rank_2025: int
    score_2025: float
    user_demand_count: int


class DepartmentForecastOut(DepartmentOut):
    """2026 tahmin bandı ve trend bilgisiyle zenginleştirilmiş bölüm çıktısı."""

    forecast_min_rank: int
    forecast_max_rank: int
    trend_status: str


class CommentOut(BaseModel):
    """Bir bölüme ait yorumun API çıktısı."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    content: str
    created_at: datetime


class CommentCreate(BaseModel):
    """Yeni yorum oluşturmak için alınan giriş şeması."""

    nickname: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)


class DepartmentDetailOut(DepartmentForecastOut):
    """Bölüm detayı: ham bilgiler, tahmin bandı ve yorumlar birlikte."""

    comments: list[CommentOut] = []


class CalculateListRequest(BaseModel):
    """Tercih listesi ihtimal hesaplama isteği."""

    user_rank: int = Field(gt=0)
    department_ids: list[int] = Field(min_length=1)


class DepartmentChanceOut(BaseModel):
    """Tercih listesindeki bir bölüm için ihtimal analizi sonucu."""

    department_id: int
    university_name: str
    department_name: str
    forecast_min_rank: int
    forecast_max_rank: int
    trend_status: str
    chance_message: str
    chance_color: str


class StatsOut(BaseModel):
    """Ana sayfadaki genel istatistik sayaçları için özet veri."""

    total_departments: int
    total_universities: int
    total_cities: int
