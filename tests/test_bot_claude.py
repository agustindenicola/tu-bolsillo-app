"""El extractor con Claude, con la API simulada (no gasta ni necesita credenciales)."""
import json
from types import SimpleNamespace

import anthropic
import pytest

import importlib

ex = importlib.import_module("tubolsillo.bot.extract")


class FakeMessages:
    def __init__(self, payload, stop="end_turn"):
        self.payload, self.stop, self.calls = payload, stop, []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


def fake_client(monkeypatch, payload, stop="end_turn"):
    msgs = FakeMessages(payload, stop)
    monkeypatch.setattr(anthropic, "Anthropic", lambda: SimpleNamespace(beta=SimpleNamespace(messages=msgs)))
    monkeypatch.delenv("TUBOLSILLO_NO_AI", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    return msgs


PROMO = {"merchant": "Tienda IA", "rubro": "ropa", "method_id": "naranjax", "pct": 20, "days": [5, 6, 5], "cap_month": 5000,
         "min_amount": None, "conditions": "Fines de semana", "valid_to": None, "confidence": 0.9}


def test_claude_request_shape_and_parsing(monkeypatch):
    msgs = fake_client(monkeypatch, {"promos": [PROMO, {**PROMO, "method_id": "inventado"}, {**PROMO, "pct": 0}]})
    promos, how = ex.extract("texto de una página", "Fuente X")
    assert how == "claude"
    assert len(promos) == 1 and promos[0]["days"] == [5, 6]          # descarta medios desconocidos y % inválidos; ordena días
    call = msgs.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in call["betas"]


def test_refusal_returns_nothing(monkeypatch):
    fake_client(monkeypatch, {"promos": [PROMO]}, stop="refusal")
    promos, how = ex.extract("texto", "X")
    assert promos == [] and how == "claude"


def test_api_error_falls_back_to_rules(monkeypatch):
    def boom():
        class M:
            def create(self, **kw):
                raise anthropic.APIConnectionError(request=None)
        return SimpleNamespace(beta=SimpleNamespace(messages=M()))
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    monkeypatch.delenv("TUBOLSILLO_NO_AI", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    promos, how = ex.extract("15% en Local Z los lunes con MODO.", "X")
    assert how == "reglas" and promos[0]["method_id"] == "modo"


def test_long_pages_are_split_not_truncated(monkeypatch):
    msgs = fake_client(monkeypatch, {"promos": []})
    ex.extract("x" * 130000, "X")
    assert len(msgs.calls) == 3
    import re
    sent = "".join(re.search(r"<pagina>\n(.*)\n</pagina>", c["messages"][0]["content"][0]["text"], re.S).group(1) for c in msgs.calls)
    assert sent == "x" * 130000                                       # todo el texto llega, en partes


@pytest.fixture(autouse=True)
def _restore_env(monkeypatch):
    yield
    monkeypatch.setenv("TUBOLSILLO_NO_AI", "1")
