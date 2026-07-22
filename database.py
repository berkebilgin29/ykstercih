"""SQLAlchemy engine, session ve declarative base tanımları."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./yks_data.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Tüm ORM modelleri için ortak taban sınıf."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency olarak kullanılacak veritabanı oturumu üretici."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Tanımlı tüm modellere göre veritabanı tablolarını oluşturur."""
    Base.metadata.create_all(bind=engine)
