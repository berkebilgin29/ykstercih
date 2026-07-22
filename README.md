# YKS Tercih & Sıralama Tahmin Portalı

Öğrencilerin üniversite bölümlerinin geçmiş yıl sıralama/puan verilerini inceleyip
2026 için tahmini kapatma sıralamasını ve kendi kazanma ihtimallerini görebildiği
bir YKS tercih asistanı. Backend FastAPI + SQLAlchemy + SQLite, frontend tek
sayfalık (SPA) bir Jinja2 şablonu üzerinde vanilla JS + Tailwind CSS + Chart.js
ile yazılmıştır.

## Özellikler

- **Gerçek veri:** Tüm bölümler YÖK Atlas'ın herkese açık tercih kılavuzu API'sinden
  indirilir (bkz. `fetch_real_data.py`) — lisans ve önlisans, 2023/2024/2025 sıralama
  ve puan verileriyle.
- **2026 tahmin motoru:** Son 3 yılın sıralama ivmesine ve sitedeki kullanıcı talebine
  göre 2026 için tahmini bir sıralama bandı ve trend yönü (`predictor.py`).
- **Kişisel öneriler:** Kullanıcı YKS sıralamasını girince, backend bu sıralamaya en
  yakın gerçek bölümleri anında listeler.
- **Kazanma ihtimali:** Girilen sıralama ile tahmin bandı kıyaslanarak
  Güvenli/Muhtemel/Zor kategorisinde renkli bir sonuç üretilir.
- **Tercih listesi:** Bölümleri listeye ekleyip toplu ihtimal analizi yapılabilir.
- **Yorumlar:** Her bölüme öğrenciler yorum bırakabilir.
- **Modern arayüz:** Koyu/açık mod, mikro etkileşimler, Chart.js ile sıralama
  grafikleri (mini trend + 2026 tahmin konisi).

## Kurulum

```bash
pip install -r requirements.txt
```

## Veritabanını doldurma

İki seçenek var — biri demo veri, diğeri YÖK Atlas'tan gerçek veri:

```bash
# Hızlı demo veri (20 örnek bölüm)
python seed_data.py

# Gerçek veri (YÖK Atlas'tan ~14.500 bölüm indirir, birkaç dakika sürebilir)
python fetch_real_data.py
```

## Çalıştırma

```bash
python main.py
```

Sunucu `http://127.0.0.1:8000` adresinde ayağa kalkar. Arayüz kök path'te (`/`),
API dokümantasyonu ise `/docs` altında yer alır.

## Proje yapısı

| Dosya | Açıklama |
|---|---|
| `database.py` | SQLAlchemy engine/session/Base tanımları |
| `models.py` | `Department` ve `Comment` ORM modelleri |
| `schemas.py` | API için Pydantic giriş/çıkış şemaları |
| `predictor.py` | 2026 tahmin bandı ve kazanma ihtimali algoritması |
| `main.py` | FastAPI uygulaması ve API endpoint'leri |
| `seed_data.py` | Demo veri ile veritabanını doldurma script'i |
| `fetch_real_data.py` | YÖK Atlas'tan gerçek veri indirme script'i |
| `templates/index.html` | Tek sayfalık frontend arayüzü |
