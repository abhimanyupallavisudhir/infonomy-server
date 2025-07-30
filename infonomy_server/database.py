from sqlmodel import create_engine, SQLModel, Session
from contextlib import contextmanager

DATABASE_URL = "sqlite:///./infonomy_server.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session

# Dependency to get the database session
def get_db():
    with get_session() as session:
        yield session
