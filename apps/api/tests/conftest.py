import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client, tmp_path, monkeypatch):
    """Registers a user, logs in, returns (client, headers, helper to create a workspace/deal)."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VALORA_STORAGE_DIR", str(tmp_path))

    client.post("/api/auth/register", json={"email": "analyst@example.com", "name": "Analyst", "password": "supersecret1"})
    resp = client.post("/api/auth/login", data={"username": "analyst@example.com", "password": "supersecret1"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers
