import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv

load_dotenv()

# =========================================================
# DATABASE URL
# Read from environment variable DATABASE_URL.
# If not set, fall back to localhost development default.
# Replace <your_password> with your PostgreSQL password in
# the .env file:
#   DATABASE_URL=postgresql+psycopg2://postgres:<your_password>@localhost:5432/cdtrs
# =========================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:your_password@localhost:5432/cdtrs"
)

# Cloud providers (e.g. Render, Railway, Neon, Supabase) often provide URLs starting with "postgres://"
# SQLAlchemy requires "postgresql+psycopg2://" or "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg2://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    DATABASE_URL,
    echo=False         # Set True for SQL query logging during debug
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# =========================================================
# DB SESSION DEPENDENCY (FastAPI)
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()