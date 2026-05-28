import os
from sqlmodel import create_engine, SQLModel, Session
from fastapi import Depends
from typing import Generator

# 1. Pull Postgres configurations from environment variables
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mydb")
# Inside the Docker network, the hostname is the service name: 'db'
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/{POSTGRES_DB}"

# 2. Create the unified SQLAlchemy/SQLModel engine
engine = create_engine(DATABASE_URL, echo=True)  # echo=True prints raw SQL to your terminal logs

# 3. Create the automation hook function to deploy tables
def init_db():
    # This magic line inspects SQLModel metadata, looks at your tables,
    # and issues "CREATE TABLE IF NOT EXISTS" commands to Postgres!
    SQLModel.metadata.create_all(engine)

# 4. Dependency helper to get a database session inside API endpoints
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session