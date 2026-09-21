1from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings

# For synchronous operations / initial lightweight or testing setups
sync_db_url = settings.database_url
if sync_db_url and sync_db_url.startswith("sqlite+aiosqlite"):
    sync_db_url = sync_db_url.replace("sqlite+aiosqlite", "sqlite")
elif sync_db_url and sync_db_url.startswith("postgresql+asyncpg"):
    sync_db_url = sync_db_url.replace("postgresql+asyncpg", "postgresql")

connect_args = {"check_same_thread": False} if sync_db_url and "sqlite" in sync_db_url else {}

engine = create_engine(sync_db_url or "sqlite:///./data/algotrade.db", connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
