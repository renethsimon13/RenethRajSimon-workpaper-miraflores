import os
import sys
import tempfile

import pytest

# Isolated database per test session, never the real one.
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _db
os.environ.pop("SEED_ON_EMPTY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from app import store  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    store.reset()
    return TestClient(app)


@pytest.fixture()
def seeded(client):
    r = client.post("/api/admin/seed", headers={"X-Person": "st-05"})
    assert r.status_code == 200
    return client


def post(c, person, type_, payload):
    return c.post("/api/events", headers={"X-Person": person}, json={"type": type_, "payload": payload})
