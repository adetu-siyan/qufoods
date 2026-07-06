import os

from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load the .env file
load_dotenv()

# Read DATABASE_URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Check that it exists
if DATABASE_URL is None:
    raise ValueError(
        "DATABASE_URL was not found. Check your .env file."
    )

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

# Create a session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


def get_session():
    return SessionLocal()