import os
import sys
import tempfile

import pytest

# base de datos aparte para las pruebas (nunca toca los datos reales) y sin IA
os.environ["TUBOLSILLO_DATA"] = tempfile.mkdtemp(prefix="tubolsillo-test-")
os.environ["TUBOLSILLO_NO_AI"] = "1"
os.environ["TUBOLSILLO_DEMO"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubolsillo.db import db  # noqa: E402
from tubolsillo.server import create_app  # noqa: E402

APP = create_app(seed_demo=True)
H = {"X-TB": "1"}


@pytest.fixture
def con():
    with db() as c:
        yield c


@pytest.fixture
def client():
    return APP.test_client()


def login(client, role="user"):
    r = client.post("/api/demo-login", json={"role": role}, headers=H)
    assert r.status_code == 200
    return client


def new_user(client, email, methods=("mercadopago",)):
    r = client.post("/api/register", json={"email": email, "password": "clave-segura-1", "name": "Prueba", "accept_terms": True}, headers=H)
    assert r.status_code == 200, r.json
    client.put("/api/me", json={"methods": list(methods), "onboarded": True}, headers=H)
    return client
