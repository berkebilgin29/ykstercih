"""2026 sıralama tahmini ve kazanma ihtimali hesaplama algoritmaları.

Not: YKS sıralamalarında sayı ne kadar KÜÇÜKSE bölüm o kadar rekabetçi/popülerdir.
Bu yüzden "sıralama numarası düşüyor" durumu popülerlik açısından bir
YÜKSELİŞ (daha çok talep görüyor) anlamına gelir; "sıralama numarası
artıyor" ise bir DÜŞÜŞ (talep azalıyor) anlamına gelir.
"""
from dataclasses import dataclass

# Trend'in "SABİT" sayılması için yıllık ortalama değişimin, son yıl
# sıralamasına oranla kalması gereken üst sınır.
STABLE_TREND_THRESHOLD_RATIO = 0.02

# Talep sayısının tahmini sıralamayı ne kadar iyileştirebileceğinin üst sınırı
# (tahmini sıralamanın en fazla %15'i kadar iyileştirme yapılabilir).
MAX_DEMAND_PULL_RATIO = 0.15

# Her 1000 kullanıcı talebinin karşılık geldiği iyileştirme oranı.
DEMAND_PULL_PER_UNIT = 0.0001

# Tahmin bandının, oynaklık sıfıra yakın olsa bile en az bu oranda geniş olması.
MIN_BAND_RATIO = 0.05


@dataclass(frozen=True)
class ForecastResult:
    """calculate_2026_forecast fonksiyonunun döndürdüğü tahmin sonucu."""

    forecast_min_rank: int
    forecast_max_rank: int
    trend_status: str


@dataclass(frozen=True)
class WinningChance:
    """calculate_winning_chance fonksiyonunun döndürdüğü ihtimal sonucu."""

    message: str
    color: str


def _determine_trend(avg_delta: float, rank_2025: int) -> str:
    """Yıllık ortalama sıralama değişimine göre trend durumunu belirler."""
    stable_threshold = rank_2025 * STABLE_TREND_THRESHOLD_RATIO
    if abs(avg_delta) <= stable_threshold:
        return "SABİT"
    if avg_delta < 0:
        return "YÜKSELİŞ"
    return "DÜŞÜŞ"


def calculate_2026_forecast(
    rank_2023: int,
    rank_2024: int,
    rank_2025: int,
    user_demand_count: int,
) -> ForecastResult:
    """Son 3 yılın sıralama verisinden 2026 tahmini bandını hesaplar.

    Trend, ardışık yıllar arasındaki ortalama sıralama değişimi (ivme)
    baz alınarak 2025 sıralamasından ileriye doğru ekstrapole edilir.
    Sitedeki kullanıcı talebi (user_demand_count) yüksekse, bölümün
    gerçekte olduğundan daha rekabetçi hale geleceği varsayılarak
    tahmini sıralama sayısı aşağı (daha iyi) çekilir.

    Returns:
        forecast_min_rank: En iyi ihtimal (en küçük/rekabetçi sıralama).
        forecast_max_rank: En kötü ihtimal (en büyük/gevşek sıralama).
        trend_status: "YÜKSELİŞ", "DÜŞÜŞ" veya "SABİT".
    """
    delta_23_24 = rank_2024 - rank_2023
    delta_24_25 = rank_2025 - rank_2024
    avg_delta = (delta_23_24 + delta_24_25) / 2

    trend_status = _determine_trend(avg_delta, rank_2025)

    base_forecast = rank_2025 + avg_delta

    demand_pull_ratio = min(user_demand_count * DEMAND_PULL_PER_UNIT, MAX_DEMAND_PULL_RATIO)
    demand_adjustment = base_forecast * demand_pull_ratio
    adjusted_forecast = base_forecast - demand_adjustment

    volatility = max(abs(delta_23_24), abs(delta_24_25))
    band_width = max(volatility, adjusted_forecast * MIN_BAND_RATIO)

    forecast_min_rank = max(1, round(adjusted_forecast - band_width / 2))
    forecast_max_rank = max(forecast_min_rank + 1, round(adjusted_forecast + band_width / 2))

    return ForecastResult(
        forecast_min_rank=forecast_min_rank,
        forecast_max_rank=forecast_max_rank,
        trend_status=trend_status,
    )


def calculate_winning_chance(
    user_rank: int,
    forecast_min_rank: int,
    forecast_max_rank: int,
) -> WinningChance:
    """Öğrencinin sıralamasını tahmini banda kıyaslayarak kazanma ihtimalini döndürür.

    Öğrenci rank < forecast_min ise sıralaması bölümün beklenen en iyi
    tahmininden bile küçük demektir, yani güvenli bir tercihtir.
    """
    if user_rank < forecast_min_rank:
        return WinningChance(message="%85 - %99 (Güvenli Liman)", color="GREEN")
    if user_rank <= forecast_max_rank:
        return WinningChance(message="%40 - %70 (Sınırda / Muhtemel)", color="YELLOW")
    return WinningChance(message="%5 - %25 (Sürpriz / Zor)", color="RED")
