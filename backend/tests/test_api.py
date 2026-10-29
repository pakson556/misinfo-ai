import json

import httpx
import pytest
import respx
from app.llm.base import ExtractedClaim, VerifyOutcome
from app.schemas import Evidence
from fastapi.testclient import TestClient


class FakeProvider:
    """Deterministic stand-in for Claude so tests need no key or network."""

    name = "fake"
    model = "fake-1"
    can_search = True

    async def extract_claims(self, text, max_claims):
        return [
            ExtractedClaim(text="5G towers spread COVID-19", quote="5G towers spread COVID-19", checkworthiness=0.9),
            ExtractedClaim(text="The WHO is based in Geneva", quote="WHO is based in Geneva", checkworthiness=0.5),
        ]

    async def verify_claim(self, claim, evidence, context, allow_search):
        if "5G" in claim:
            return VerifyOutcome(
                "REFUTED",
                0.92,
                "Fact-checkers and the WHO say radio waves cannot carry viruses.",
                stances={0: "refutes"} if evidence else {},
                extra_evidence=[
                    Evidence(
                        title="WHO mythbusters",
                        url="https://www.who.int/myths",
                        domain="who.int",
                        kind="government",
                        credibility=0.88,
                        snippet="5G mobile networks DO NOT spread COVID-19",
                    )
                ],
            )
        return VerifyOutcome("SUPPORTED", 0.85, "The WHO headquarters is in Geneva.")

    async def summarize(self, payload):
        return ("A viral 5G-COVID claim is false", "The main claim is contradicted by health authorities.")


TEXT = "URGENT!!! 5G towers spread COVID-19 and the WHO is based in Geneva. Share this before they delete it!"


@pytest.fixture
def client(monkeypatch):
    import app.llm as llm_mod
    import app.main as main_mod
    import app.pipeline.orchestrator as orch

    fake = FakeProvider()
    monkeypatch.setattr(orch, "get_provider", lambda: fake)
    monkeypatch.setattr(main_mod, "get_provider", lambda: fake)
    monkeypatch.setattr(llm_mod, "get_provider", lambda: fake)
    with TestClient(main_mod.app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["llm_provider"] == "fake"


def test_analyze_end_to_end_and_history(client):
    r = client.post("/api/analyze", json={"text": TEXT, "use_web": True})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["overall"] == "LIKELY_FALSE"
    assert res["headline"] == "A viral 5G-COVID claim is false"
    assert res["claims"][0]["verdict"] == "REFUTED"
    assert any(e["domain"] == "who.int" for e in res["claims"][0]["evidence"])
    assert {t["id"] for t in res["tactics"]} >= {"virality_call", "urgency"}
    span = res["claims"][0]["claim"]["span"]
    assert TEXT[span["start"] : span["end"]] == "5G towers spread COVID-19"

    hist = client.get("/api/history").json()
    assert hist[0]["id"] == res["id"]
    assert client.get(f"/api/history/{res['id']}").json()["overall"] == "LIKELY_FALSE"
    stats = client.get("/api/stats").json()
    assert stats["total"] >= 1 and stats["by_claim_verdict"]["REFUTED"] >= 1
    assert client.delete(f"/api/history/{res['id']}").status_code == 200
    assert client.get(f"/api/history/{res['id']}").status_code == 404


def _parse_sse(body: str):
    events, cur = [], {}
    for line in body.splitlines():
        if line.startswith("event:"):
            cur["event"] = line[6:].strip()
        elif line.startswith("data:"):
            cur["data"] = json.loads(line[5:].strip())
        elif not line.strip() and cur:
            events.append(cur)
            cur = {}
    if cur:
        events.append(cur)
    return [e for e in events if "event" in e]


def test_stream_emits_ordered_events(client):
    with client.stream("POST", "/api/analyze/stream", json={"text": TEXT}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    names = [e["event"] for e in _parse_sse(body)]
    assert names[0] == "input"
    assert names.index("claims") < names.index("claim_result") < names.index("result")
    assert names.count("claim_result") == 2
    assert names[-1] == "result"


def test_validation_requires_exactly_one_input(client):
    assert client.post("/api/analyze", json={}).status_code == 422
    assert client.post("/api/analyze", json={"text": "hi", "url": "https://example.com"}).status_code == 422


def test_ssrf_blocked(client):
    r = client.post("/api/analyze", json={"url": "http://127.0.0.1:8000/api/health"})
    assert r.status_code == 422
    assert "private" in r.json()["detail"]


def test_llm_failure_falls_back_gracefully(client, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("api down")

    monkeypatch.setattr(FakeProvider, "verify_claim", boom)
    res = client.post("/api/analyze", json={"text": TEXT}).json()
    assert all(c["verdict"] == "UNVERIFIABLE" for c in res["claims"])
    assert res["overall"] == "UNVERIFIED"
    assert any("fact-check matching" in w for w in res["pipeline"]["warnings"])


@respx.mock
@pytest.mark.asyncio
async def test_google_factcheck_parsing_and_isolated_failures(monkeypatch):
    monkeypatch.setenv("GOOGLE_FACTCHECK_API_KEY", "k")
    monkeypatch.setenv("ENABLE_WIKIPEDIA", "true")
    from app.config import get_settings
    from app.services import http as http_mod

    get_settings.cache_clear()
    http_mod.cache().clear()
    respx.get(url__startswith="https://factchecktools.googleapis.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "claims": [
                    {
                        "text": "5G spreads coronavirus",
                        "claimDate": "2020-04-01T00:00:00Z",
                        "claimReview": [
                            {
                                "publisher": {"name": "Full Fact", "site": "fullfact.org"},
                                "url": "https://fullfact.org/health/5g-coronavirus/",
                                "title": "5G does not cause coronavirus",
                                "textualRating": "False",
                                "reviewDate": "2020-04-02T00:00:00Z",
                            }
                        ],
                    }
                ]
            },
        )
    )
    respx.get(url__startswith="https://en.wikipedia.org").mock(return_value=httpx.Response(503))

    from app.pipeline.retrieval import gather_evidence

    ev, used, warnings = await gather_evidence("5G spreads coronavirus")
    assert used == ["google_factcheck"]
    assert ev[0].kind == "factcheck" and ev[0].rating == "False" and ev[0].publisher == "Full Fact"
    assert any("wikipedia" in w for w in warnings)
    await http_mod.aclose()
