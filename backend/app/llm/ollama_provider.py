"""
A free AI model running on your own machine via Ollama (https://ollama.com).

Free and private (nothing leaves your computer), but slower, less accurate than
Claude, and with no web search of its own. It still gets the Google Fact
Check / Wikipedia evidence. To use it: install Ollama, run `ollama pull llama3.1:8b`,
then set LLM_PROVIDER=ollama in backend/.env.

Ollama's "format" option forces the reply to match our JSON schema.
"""

from __future__ import annotations

import json
from datetime import date

from ..schemas import Evidence
from ..services import http
from .base import (
    CLAIMS_SCHEMA,
    EXTRACT_SYSTEM,
    SUMMARY_SCHEMA,
    SUMMARY_SYSTEM,
    VERDICT_SCHEMA,
    VERIFY_SYSTEM,
    ExtractedClaim,
    VerifyOutcome,
    clamp01,
    format_evidence,
)


class OllamaProvider:
    name = "ollama"
    can_search = False

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def _chat(self, system: str, user: str, schema: dict) -> dict:
        """Send one question to the local model and get back JSON matching `schema`."""
        r = await http.client().post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "format": schema,  # Ollama structured outputs
                "options": {"temperature": 0.1},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=120,
        )
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])

    async def extract_claims(self, text: str, max_claims: int) -> list[ExtractedClaim]:
        data = await self._chat(EXTRACT_SYSTEM.format(max_claims=max_claims), f"<content>\n{text}\n</content>", CLAIMS_SCHEMA)
        return [
            ExtractedClaim(
                text=str(c["text"]).strip(), quote=str(c.get("quote", "")), checkworthiness=clamp01(c.get("checkworthiness", 0.5))
            )
            for c in (data.get("claims") or [])[:max_claims]
            if str(c.get("text", "")).strip()
        ]

    async def verify_claim(self, claim: str, evidence: list[Evidence], context: str, allow_search: bool) -> VerifyOutcome:
        system = VERIFY_SYSTEM.format(today=date.today().isoformat(), web_clause="").replace(
            "When done, call the report_verdict tool exactly once.", "Respond with JSON only."
        )
        data = await self._chat(
            system,
            f"<claim>{claim}</claim>\n<original_context>{context[:1500]}</original_context>\n<evidence>\n{format_evidence(evidence)}\n</evidence>",
            VERDICT_SCHEMA,
        )
        stances = {}
        for j in data.get("evidence_judgements") or []:
            try:
                i = int(j["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= i < len(evidence):
                stances[i] = j.get("stance", "neutral")
        v = data.get("verdict", "UNVERIFIABLE")
        # A small local model with no evidence would just be guessing from memory: don't let it.
        if not evidence and v != "UNVERIFIABLE":
            v, data["confidence"] = "UNVERIFIABLE", 0.2
        return VerifyOutcome(
            verdict=v if v in {"SUPPORTED", "REFUTED", "MIXED", "UNVERIFIABLE"} else "UNVERIFIABLE",
            confidence=clamp01(data.get("confidence", 0)),
            reasoning=str(data.get("reasoning", "")),
            stances=stances,
        )

    async def summarize(self, payload: str) -> tuple[str, str] | None:
        data = await self._chat(SUMMARY_SYSTEM, payload, SUMMARY_SCHEMA)
        h, s = str(data.get("headline", "")).strip(), str(data.get("summary", "")).strip()
        return (h, s) if h and s else None
