"""
Claude (Anthropic's API) as the AI. The best-quality option; needs ANTHROPIC_API_KEY.

TWO MODELS, TO BALANCE COST AND QUALITY
    LLM_FAST_MODEL (Haiku):  finding claims, writing summaries   (quick, cheap)
    LLM_MODEL      (Opus):   judging each claim                  (careful, the hard part)

TOOLS = STRUCTURED ANSWERS
    We give Claude a "tool" (e.g. report_verdict) whose input is our JSON schema,
    and tell it to call that tool. Its "call" IS the answer, already in the exact
    shape we need. Nothing is executed; it's just a reliable way to get JSON.

CLAUDE'S OWN WEB SEARCH
    When judging, Claude can also run web searches (Anthropic runs them; ~$10 per
    1,000). Sources it finds are added to the claim's evidence. Capped by
    LLM_MAX_SEARCHES_PER_CLAIM.
"""

from __future__ import annotations

import logging
from datetime import date

from ..schemas import Evidence
from ..services.sources import classify, domain_of
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

log = logging.getLogger(__name__)


def _block_get(block, key, default=None):
    """Read a field from a response block, whether the SDK gave us an object or a dict."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


class AnthropicProvider:
    name = "anthropic"
    can_search = True

    def __init__(self, api_key: str, model: str, fast_model: str, web_search: bool, max_searches: int):
        # The official Anthropic Python SDK. Retries twice on temporary errors.
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key, max_retries=2, timeout=60.0)
        self.model = model
        self.fast_model = fast_model
        self.web_search = web_search
        self.max_searches = max_searches

    async def _forced_tool(self, *, model: str, system: str, user: str, tool_name: str, schema: dict, max_tokens: int):
        """Ask Claude one question and force the answer into `schema` (see TOOLS above)."""
        resp = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": tool_name, "description": f"Submit the {tool_name} result.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in resp.content:
            if _block_get(block, "type") == "tool_use" and _block_get(block, "name") == tool_name:
                return _block_get(block, "input") or {}
        raise RuntimeError(f"Model did not return {tool_name}")

    # ------------------------------------------------------------------ claims
    async def extract_claims(self, text: str, max_claims: int) -> list[ExtractedClaim]:
        data = await self._forced_tool(
            model=self.fast_model,
            system=EXTRACT_SYSTEM.format(max_claims=max_claims),
            user=f"<content>\n{text}\n</content>",
            tool_name="submit_claims",
            schema=CLAIMS_SCHEMA,
            max_tokens=1500,
        )
        out = []
        for c in (data.get("claims") or [])[:max_claims]:
            t = str(c.get("text", "")).strip()
            if t:
                out.append(
                    ExtractedClaim(text=t, quote=str(c.get("quote", "")), checkworthiness=clamp01(c.get("checkworthiness", 0.5)))
                )
        return out

    # ------------------------------------------------------------------ verify
    async def verify_claim(self, claim: str, evidence: list[Evidence], context: str, allow_search: bool) -> VerifyOutcome:
        """
        Judge one claim. This is a short back-and-forth ("agentic loop"):
          1. Send the claim + our evidence. Claude may run web searches first.
          2. Collect any sources its searches found.
          3. When it calls report_verdict, that's the answer.
        After 3 rounds we force it to decide, so a check can't loop forever.
        """
        use_search = allow_search and self.web_search
        system = VERIFY_SYSTEM.format(
            today=date.today().isoformat(),
            web_clause=", and run web searches if it is not enough (prefer fact-checkers and primary sources)"
            if use_search
            else "",
        )
        user = (
            f"<claim>{claim}</claim>\n\n"
            f"<original_context>{context[:1500]}</original_context>\n\n"
            f"<evidence>\n{format_evidence(evidence)}\n</evidence>"
        )
        tools: list[dict] = [
            {
                "name": "report_verdict",
                "description": "Report the final verdict for the claim. Call exactly once, at the end.",
                "input_schema": VERDICT_SCHEMA,
            }
        ]
        if use_search:
            tools.insert(0, {"type": "web_search_20250305", "name": "web_search", "max_uses": self.max_searches})

        messages: list[dict] = [{"role": "user", "content": user}]
        found: dict[str, Evidence] = {}
        searches = 0

        for step in range(5):
            force = step >= 3  # after 3 rounds: no more searching, give a verdict now
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=2500,
                system=system,
                messages=messages,
                tools=tools,
                tool_choice={"type": "tool", "name": "report_verdict"} if force else {"type": "auto"},
            )
            verdict_input = None
            for block in resp.content:
                btype = _block_get(block, "type")
                # Walk through Claude's reply piece by piece.
                if btype == "server_tool_use":  # Claude ran a web search
                    searches += 1
                elif btype == "web_search_tool_result":  # the search results: keep them as evidence
                    content = _block_get(block, "content")
                    if isinstance(content, list):
                        for item in content:
                            url = _block_get(item, "url", "")
                            if url and url not in found:
                                kind, cred = classify(url)
                                found[url] = Evidence(
                                    title=_block_get(item, "title", "") or "",
                                    url=url,
                                    domain=domain_of(url),
                                    kind=kind,
                                    credibility=cred,
                                    published=_block_get(item, "page_age"),
                                )
                elif btype == "text":
                    for cit in _block_get(block, "citations") or []:
                        url = _block_get(cit, "url", "")
                        if url in found and not found[url].snippet:
                            found[url].snippet = _block_get(cit, "cited_text", "") or ""
                elif btype == "tool_use" and _block_get(block, "name") == "report_verdict":
                    verdict_input = _block_get(block, "input") or {}

            if verdict_input is not None:
                return self._outcome(verdict_input, evidence, found, searches)

            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            # Model ended without reporting; nudge it.
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": "Now call report_verdict with your final judgement."})

        raise RuntimeError("Verification did not converge")

    def _outcome(self, data: dict, evidence: list[Evidence], found: dict[str, Evidence], searches: int) -> VerifyOutcome:
        """Turn Claude's report_verdict answer into a VerifyOutcome, double-checking every value."""
        stances: dict[int, str] = {}
        for j in data.get("evidence_judgements") or []:
            try:
                idx = int(j.get("id"))
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(evidence):
                stances[idx] = j.get("stance", "neutral")
        # Only keep self-searched sources that were actually cited (have a snippet) or are high quality.
        extra = [e for e in found.values() if e.snippet or e.credibility >= 0.8][:8]
        verdict = data.get("verdict", "UNVERIFIABLE")
        if verdict not in {"SUPPORTED", "REFUTED", "MIXED", "UNVERIFIABLE"}:
            verdict = "UNVERIFIABLE"
        return VerifyOutcome(
            verdict=verdict,
            confidence=clamp01(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")).strip(),
            stances=stances,
            extra_evidence=extra,
            searches=searches,
        )

    # ------------------------------------------------------------------ summary
    async def summarize(self, payload: str) -> tuple[str, str] | None:
        data = await self._forced_tool(
            model=self.fast_model,
            system=SUMMARY_SYSTEM,
            user=payload,
            tool_name="submit_summary",
            schema=SUMMARY_SCHEMA,
            max_tokens=600,
        )
        h, s = str(data.get("headline", "")).strip(), str(data.get("summary", "")).strip()
        return (h, s) if h and s else None
