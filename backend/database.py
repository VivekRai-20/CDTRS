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