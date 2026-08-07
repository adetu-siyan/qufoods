import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ----------------------------------------------------
# Load environment variables
# ----------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL was not found in the .env file.")

# ----------------------------------------------------
# Logging configuration
# ----------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/etl.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ----------------------------------------------------
# Database Manager
# ----------------------------------------------------

class DatabaseManager:

    def __init__(self):
        self.engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            future=True
        )

        self.Session = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False
        )

    def get_session(self):
        """Return a new SQLAlchemy session."""
        return self.Session()

    def test_connection(self):
        """Test that the database is reachable."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            logger.info("Connected to Neon successfully.")
            print("Connected to Neon successfully!")

        except Exception as e:
            logger.exception("Database connection failed.")
            raise e

    def dispose(self):
        """Close all database connections."""
        self.engine.dispose()


    