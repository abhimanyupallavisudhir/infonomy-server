from sqlmodel import create_engine, SQLModel, Session
from contextlib import contextmanager
from infonomy_server.logging_config import database_logger, log_business_event

DATABASE_URL = "sqlite:///./infonomy_server.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=True)

def create_db_and_tables():
    log_business_event(database_logger, "database_initialization", parameters={
        "database_url": DATABASE_URL
    })
    SQLModel.metadata.create_all(engine)
    log_business_event(database_logger, "database_tables_created", parameters={
        "tables": list(SQLModel.metadata.tables.keys())
    })

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session

# Dependency to get the database session
def get_db():
    with get_session() as session:
        yield session
