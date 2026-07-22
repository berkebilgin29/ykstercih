"""YÖK Atlas'ın herkese açık tercih kılavuzu arama uç noktasından gerçek üniversite
program verilerini indirip Department tablosuna yükleyen script.

Veri kaynağı: https://yokatlas.yok.gov.tr/api/tercih-kilavuz/search
Bu, YÖK Atlas'ın kendi web arayüzünün arama-yazdıkça-filtrele özelliğinin kullandığı,
kimlik doğrulaması gerektirmeyen herkese açık JSON uç noktasıdır (requests ile
doğrudan çağrılır; üçüncü parti bir sarmalayıcı pakete ihtiyaç duyulmaz).

YÖK Atlas'ın "geçmiş yıl kontenjanı" alanı yayınlanmadığından, quota_2025 için
2025'te fiilen yerleştirilen öğrenci sayısı (gkY1: genel kontenjandan yerleşen)
kullanılır; bu, gerçek ve doğrulanabilir bir veridir.

Çalıştırmak için: python fetch_real_data.py
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from database import SessionLocal, engine, init_db
from models import Comment, Department

SEARCH_URL = "https://yokatlas.yok.gov.tr/api/tercih-kilavuz/search"
PAGE_SIZE = 1000
REQUEST_DELAY_SECONDS = 0.4
MAX_RETRIES = 3

# YÖK Atlas'taki birim türü kodları: 46 = Lisans (4 yıllık), 47 = Önlisans (2 yıllık)
BIRIM_TURU_IDS = (46, 47)

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "yks-tercih-tahmin-fetcher/1.0 (egitim amacli veri toplama)",
}

# Türkçe büyük/küçük harf dönüşümünde İ/I - i/ı ayrımını doğru yapan çeviri tabloları
_TR_TO_LOWER = str.maketrans("İIÖÇŞĞÜ", "iıöçşğü")
_TR_TO_UPPER = str.maketrans("iıöçşğü", "İIÖÇŞĞÜ")


def _turkish_title_case(text: str) -> str:
    """Tamamı büyük harfle gelen Türkçe metni başlık haline getirir (İ/I ayrımına dikkat ederek).

    "(ankara)" gibi parantezle başlayan parçalarda da ilk harfi bulup büyütür.
    """
    lowered = text.translate(_TR_TO_LOWER).lower()
    words = []
    for word in lowered.split(" "):
        for i, char in enumerate(word):
            if char.isalpha():
                word = word[:i] + char.translate(_TR_TO_UPPER).upper() + word[i + 1 :]
                break
        words.append(word)
    return " ".join(words)


def _build_payload(birim_turu_id: int, page: int) -> dict[str, Any]:
    return {
        "filters": {
            "puanTuru": None,
            "universiteId": [],
            "birimGrupId": [],
            "ilKodu": [],
            "birimTuruId": birim_turu_id,
            "universiteTuru": None,
            "bursOraniId": None,
            "ogrenimTuruId": None,
            "kilavuzKodu": None,
            "minBasariSirasi": None,
            "maxBasariSirasi": None,
        },
        "page": page,
        "size": PAGE_SIZE,
        "sortBy": "basariSirasi",
        "direction": "ASC",
    }


def _fetch_page(session: requests.Session, birim_turu_id: int, page: int) -> dict[str, Any]:
    """Tek bir sayfayı indirir; 429/418 (rate limit) durumunda bekleyip yeniden dener."""
    for attempt in range(1, MAX_RETRIES + 1):
        response = session.post(
            SEARCH_URL, json=_build_payload(birim_turu_id, page), headers=HEADERS, timeout=30
        )
        if response.status_code in (418, 429) and attempt < MAX_RETRIES:
            time.sleep(2 * attempt)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"birimTuruId={birim_turu_id} sayfa={page} indirilemedi (rate limit).")


def fetch_all_programs() -> list[dict[str, Any]]:
    """Lisans ve önlisans kapsamındaki tüm programların ham YÖK Atlas kayıtlarını indirir."""
    records: list[dict[str, Any]] = []
    with requests.Session() as session:
        for birim_turu_id in BIRIM_TURU_IDS:
            page = 0
            while True:
                data = _fetch_page(session, birim_turu_id, page)
                records.extend(data["content"])
                print(
                    f"  birimTuruId={birim_turu_id}: sayfa {page + 1}/{data['totalPages']} "
                    f"({len(data['content'])} kayıt)"
                )
                if data["last"]:
                    break
                page += 1
                time.sleep(REQUEST_DELAY_SECONDS)
    return records


def _positive_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _extract_department_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Ham bir YÖK Atlas kaydını Department şemasına dönüştürür; veri eksikse None döner."""
    rank_2023 = _positive_int(raw.get("basariSirasi3"))
    rank_2024 = _positive_int(raw.get("basariSirasi2"))
    rank_2025 = _positive_int(raw.get("basariSirasi1"))
    score_2025 = _positive_float(raw.get("minPuan1"))
    quota_2025 = _positive_int(raw.get("gkY1"))

    if None in (rank_2023, rank_2024, rank_2025, score_2025, quota_2025):
        return None

    university_turu = raw.get("universiteTuru")
    burs_orani_adi = raw.get("bursOraniAdi")
    ogrenim_turu_adi = raw.get("ogrenimTuruAdi") or "Örgün Öğretim"
    education_type = (
        burs_orani_adi if university_turu == "VAKIF" and burs_orani_adi else ogrenim_turu_adi
    )

    faculty_name = raw.get("fymkAdi") or raw.get("birimGrupAdi") or raw["birimAdi"]
    city = raw.get("ilAdi") or raw.get("uniIlAdi") or "-"

    return {
        "kilavuz_kodu": raw["kilavuzKodu"],
        "university_name": _turkish_title_case(raw["universiteAdi"]),
        "faculty_name": _turkish_title_case(faculty_name),
        "department_name": _turkish_title_case(raw["birimAdi"]),
        "score_type": raw.get("puanTuru") or "TYT",
        "education_type": _turkish_title_case(education_type),
        "city": _turkish_title_case(city),
        "quota_2025": quota_2025,
        "rank_2023": rank_2023,
        "rank_2024": rank_2024,
        "rank_2025": rank_2025,
        "score_2025": score_2025,
        "user_demand_count": 0,
    }


def build_dataframe(raw_records: list[dict[str, Any]]) -> pd.DataFrame:
    """Ham kayıtları temizler, eksik verili satırları eler ve tekilleştirir."""
    rows = [row for raw in raw_records if (row := _extract_department_row(raw)) is not None]
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["kilavuz_kodu"]).drop(columns=["kilavuz_kodu"])
    return df.reset_index(drop=True)


def load_into_database(df: pd.DataFrame) -> None:
    """departments tablosunu (ve bağlı yorumları) temizleyip gerçek verilerle doldurur."""
    init_db()
    db = SessionLocal()
    try:
        db.query(Comment).delete()
        db.query(Department).delete()
        db.commit()
    finally:
        db.close()

    with engine.begin() as connection:
        df.to_sql("departments", connection, if_exists="append", index=False)


def main() -> None:
    print("YÖK Atlas'tan lisans (4 yıllık) ve önlisans (2 yıllık) program verileri indiriliyor...")
    raw_records = fetch_all_programs()
    print(f"Toplam {len(raw_records)} ham kayıt indirildi.")

    df = build_dataframe(raw_records)
    print(f"2023/2024/2025 verisi eksiksiz olan {len(df)} gerçek bölüm kaydı bulundu.")

    load_into_database(df)

    db = SessionLocal()
    try:
        total = db.query(Department).count()
        print(f"Veritabanına toplam {total} gerçek bölüm kaydı yüklendi.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
