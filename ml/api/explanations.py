"""
LLM-based explanation generation using Ollama.
Provides offline explanations without internet verification.
"""

import json
import urllib.request
import re
from typing import Dict, Any, Optional, List

# Ollama configuration
OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.1:8b"


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
    """
    Make JSON POST request to Ollama API.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)


def _clamp01(x: float) -> float:
    """Clamp value between 0 and 1"""
    try:
        v = float(x)
        return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
    except Exception:
        return 0.0


def _risk_level_from_prob(prob_pos: float) -> str:
    """
    Determine risk level using the same thresholds as the frontend.
    """
    prob_percent = int(round(prob_pos * 100))
    if prob_percent >= 45:
        return "high"
    if prob_percent >= 15:
        return "medium"
    return "low"


def _default_guidance_for_risk(risk_level: str) -> str:
    r = str(risk_level or "medium").lower()
    if r == "high":
        return "High-risk signal. Do not share until the claim has been checked against trusted primary sources."
    if r == "medium":
        return "Medium-risk signal. Verify key claims using trusted sources before sharing."
    return "Low-risk signal. Sharing risk appears lower, but still verify if the claim is high-impact or time-sensitive."


def _guidance_for_current_risk(guidance: str, risk_level: str) -> str:
    """
    Prevent stale LOW-risk guidance from being reused when the current case is MEDIUM/HIGH.
    """
    incoming = (guidance or "").strip()
    if not incoming:
        return _default_guidance_for_risk(risk_level)

    low_markers = [
        "low-risk signal",
        "sharing risk appears lower",
    ]
    medium_markers = [
        "medium-risk signal",
        "verify key claims",
    ]
    high_markers = [
        "high-risk signal",
        "do not share until",
    ]

    lowered = incoming.lower()

    if risk_level == "high":
        if any(m in lowered for m in low_markers + medium_markers):
            return _default_guidance_for_risk("high")
        return incoming

    if risk_level == "medium":
        if any(m in lowered for m in low_markers) and not any(m in lowered for m in medium_markers):
            return _default_guidance_for_risk("medium")
        return incoming

    # low
    if any(m in lowered for m in high_markers):
        return _default_guidance_for_risk("low")
    return incoming


def _build_concern_sentence(
    risk_level: str,
    stance: str,
    triggers: Optional[List[Dict]] = None,
    key_phrases: Optional[List[Dict]] = None,
) -> str:
    triggers = triggers or []
    key_phrases = key_phrases or []

    trigger_names = [str(t.get("name", "")).strip() for t in triggers[:2] if str(t.get("name", "")).strip()]
    phrases = [f"\"{p['phrase']}\"" for p in key_phrases[:2] if isinstance(p, dict) and p.get("phrase")]

    if risk_level == "low":
        if stance in {"credible", "warning", "debunking"}:
            return (
                "However, the wording appears broadly consistent with credible or corrective information, "
                "even though the text itself does not present detailed citations."
            )
        if phrases:
            return (
                f"However, the wording remains generally consistent with established information, with phrases such as "
                f"{', '.join(phrases)} suggesting an informational rather than misleading tone."
            )
        return (
            "However, the wording appears broadly consistent with established information, even though the text itself does not include detailed supporting citations."
        )

    if risk_level == "medium":
        if trigger_names:
            joined = " and ".join(name.lower() for name in trigger_names[:2])
            return (
                f"However, some aspects of the language, including {joined}, introduce uncertainty about how reliably the claims are supported."
            )
        if phrases:
            return (
                f"However, some phrases such as {', '.join(phrases)} may require additional context or supporting evidence to assess the claims confidently."
            )
        return (
            "However, some parts of the message lack enough context or supporting detail, which makes the credibility of the claims less certain."
        )

    if trigger_names:
        joined = " and ".join(name.lower() for name in trigger_names[:2])
        return (
            f"However, the language pattern, including {joined}, raises concerns about the credibility and reliability of these claims."
        )
    if phrases:
        return (
            f"However, phrases such as {', '.join(phrases)} raise concerns that the claims may be framed in a misleading or unsupported way."
        )
    return (
        "However, the lack of verifiable sourcing and the style of the message raise concerns about the credibility of these claims."
    )


def _build_implication_sentence(
    risk_level: str,
    stance: str,
    phrase_detail: str = "",
) -> str:
    if risk_level == "high":
        return (
            f"This suggests that the report may be based on unverified claims or biased interpretations rather than verifiable evidence{phrase_detail}."
        )

    if risk_level == "medium":
        return (
            f"This suggests that the content contains elements that could be either factual or misleading without further verification{phrase_detail}."
        )

    if stance in {"credible", "warning", "debunking"}:
        return (
            "This suggests that the content is more likely to reflect established knowledge, corrective framing, or responsible discussion rather than misinformation."
        )

    return (
        "This suggests that the content is more likely to reflect generally reliable or widely accepted information, although important claims should still be checked where necessary."
    )


def _clean_summary_for_risk(
    summary: str,
    risk_level_text: str,
    prob_percent: int,
    stance: str = "neutral",
) -> str:
    """
    Clean and normalize LLM output without corrupting percentages that belong
    to the original claim text (e.g. "10% of the brain").
    """
    if not summary:
        return summary

    summary = re.sub(r"\bhigh risk\b", f"{risk_level_text} risk", summary, flags=re.IGNORECASE)
    summary = re.sub(r"\bmedium risk\b", f"{risk_level_text} risk", summary, flags=re.IGNORECASE)
    summary = re.sub(r"\blow risk\b", f"{risk_level_text} risk", summary, flags=re.IGNORECASE)

    # Only replace the percentage when it appears in the specific probability phrase.
    summary = re.sub(
        r"(estimated probability of\s*)\d+%",
        rf"\g<1>{prob_percent}%",
        summary,
        flags=re.IGNORECASE,
        count=1,
    )

    # Also normalise this alternative wording if the LLM uses it.
    summary = re.sub(
        r"(estimated misinformation likelihood is\s*)\d+%",
        rf"\g<1>{prob_percent}%",
        summary,
        flags=re.IGNORECASE,
        count=1,
    )

    # IMPORTANT:
    # Do NOT replace the first generic percentage in the text.
    # That was corrupting factual claim text like "10% of the brain" into "17%".

    if risk_level_text == "low":
        summary = re.sub(
            r"However,\s*the lack of (official statements?|verifiable sources?|specific details?|specific data or sources?) raises concerns about the credibility of these claims\.",
            "However, the wording appears broadly consistent with established information, even if the text itself does not provide detailed supporting citations.",
            summary,
            flags=re.IGNORECASE,
        )
        summary = re.sub(
            r"raises concerns about the credibility of these claims",
            "does not by itself reduce the overall credibility of the message",
            summary,
            flags=re.IGNORECASE,
        )

        if stance in {"credible", "warning", "debunking"}:
            summary = re.sub(
                r"This suggests that the report may be based on speculation or biased interpretations rather than verifiable evidence\.",
                "This suggests that the content is more likely to reflect corrective, credible, or well-established information rather than misinformation.",
                summary,
                flags=re.IGNORECASE,
            )

    return summary.strip()


def _build_explanation_prompt(
    text: str,
    verdict: str,
    risk_band: str,
    prob_pos: float,
    prob_neg: float,
    early_prob: Optional[float],
    signals: Dict[str, Any],
    guidance: str,
    stance: str = "neutral",
    triggers: List[Dict] = None,
    key_phrases: List[Dict] = None,
) -> str:
    triggers = triggers or []
    key_phrases = key_phrases or []

    trigger_text = ""
    if triggers:
        trigger_text = "Detected patterns:\n"
        for t in triggers[:3]:
            trigger_text += (
                f"- {t.get('name', 'Unknown')}: {int(t.get('score', 0) * 100)}% - "
                f"{t.get('explanation', '')}\n"
            )

    key_phrases_text = ""
    if key_phrases:
        phrase_words = [f"\"{p['phrase']}\"" for p in key_phrases[:3] if isinstance(p, dict) and p.get("phrase")]
        if phrase_words:
            key_phrases_text = f"Key phrases detected: {', '.join(phrase_words)}."

    if stance == "debunking":
        stance_context = (
            "This is fact-checking or educational content that discusses misinformation rather than spreading it."
        )
    elif stance == "spreading":
        stance_context = "This content shows patterns of spreading unverified claims."
    elif stance == "warning":
        stance_context = "This content warns about potential misinformation."
    elif stance == "satire":
        stance_context = "This is satirical or parody content."
    elif stance == "credible":
        stance_context = "This content cites official or credible information."
    else:
        stance_context = "This content appears neutral in tone."

    prob_percent = int(round(prob_pos * 100))
    risk_level_text = _risk_level_from_prob(prob_pos)
    guidance = _guidance_for_current_risk(guidance, risk_level_text)

    if risk_level_text == "low":
        credibility_instruction = (
            "IMPORTANT: Because the risk is LOW, do not use strongly negative wording such as "
            "'raises concerns about credibility', 'unverified', or 'speculation' unless the text clearly deserves it. "
            "Frame the explanation as broadly consistent, generally reliable, or aligned with established knowledge."
        )
    elif risk_level_text == "medium":
        credibility_instruction = (
            "IMPORTANT: Because the risk is MEDIUM, use balanced wording. Do not overstate either certainty or falsehood."
        )
    else:
        credibility_instruction = (
            "IMPORTANT: Because the risk is HIGH, clearly explain that the content shows patterns associated with misleading or unsupported claims."
        )

    example_concern = _build_concern_sentence(
        risk_level=risk_level_text,
        stance=stance,
        triggers=triggers,
        key_phrases=key_phrases,
    )

    example_implication = _build_implication_sentence(
        risk_level=risk_level_text,
        stance=stance,
        phrase_detail="",
    )

    return f"""
You are an OFFLINE explanation module for a misinformation-risk detection system.
You do NOT have internet access and MUST NOT claim you verified real-world facts.

Your job: Write a DETAILED, report-style explanation based ONLY on the input text and model outputs.
The explanation MUST be 4-5 sentences long.

Return ONLY VALID JSON. No markdown. No extra text.

CONTEXT: {stance_context}

INPUT_TEXT:
{text}

MODEL_OUTPUT:
- verdict: {verdict}
- risk_band: {risk_band}
- prob_misinformation: {prob_pos:.6f} ({prob_percent}%)
- prob_non_misinformation: {prob_neg:.6f}
- spread_potential: {early_prob if early_prob is not None else 'null'}
- {key_phrases_text}

{trigger_text}

{credibility_instruction}

IMPORTANT FACTUAL WRITING RULE:
- If the input text contains a percentage as part of the claim itself (for example "10% of the brain"),
  do NOT replace that claim percentage with the model probability.
- The model probability ({prob_percent}%) should only appear when describing misinformation risk,
  not when restating the user's claim.

Return JSON exactly matching this schema:
{{
  "user_summary": "A DETAILED paragraph of 4-5 sentences. Sentence 1 should summarise the main topic or claim. Sentence 2 should describe a credibility/context concern OR supporting context in a way that matches the risk level. Sentence 3 should state the {risk_level_text} risk of misinformation with an estimated probability of {prob_percent}%. Sentence 4 should explain what that means. Sentence 5 should give practical guidance.",
  "user_reasons": ["2-3 bullet points explaining the main signals"],
  "user_guidance": "{guidance}",
  "final_explanation": "The same as user_summary (for backward compatibility)",
  "signals": {{}}
}}

EXAMPLE OF APPROPRIATE WORDING FOR THIS CASE:
"The text reports on the main claim in a clear and informative way. {example_concern} The model outputs indicate a {risk_level_text} risk of misinformation, with an estimated probability of {prob_percent}%. {example_implication} As such, it is essential to {guidance if guidance else _default_guidance_for_risk(risk_level_text)}"

CRITICAL FORMATTING RULES:
- The explanation MUST be 4-5 sentences long
- Use professional, neutral language
- Keep the explanation consistent with the reported probability and risk level
- Do not make low-risk content sound misleading without strong textual evidence
"""


def generate_explanation(
    text: str,
    verdict: str,
    risk_band: str,
    prob_pos: float,
    prob_neg: float,
    early_prob: Optional[float] = None,
    signals: Optional[Dict[str, Any]] = None,
    guidance: str = "",
    stance: str = "neutral",
    triggers: Optional[List[Dict]] = None,
    key_phrases: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    signals = signals or {}
    triggers = triggers or []
    key_phrases = key_phrases or []

    prob_percent = int(round(prob_pos * 100))
    risk_level_text = _risk_level_from_prob(prob_pos)
    forced_risk_band = risk_level_text.upper()
    safe_guidance = _guidance_for_current_risk(guidance, risk_level_text)

    prompt = _build_explanation_prompt(
        text=text,
        verdict=verdict,
        risk_band=forced_risk_band,
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        early_prob=early_prob,
        signals=signals,
        guidance=safe_guidance,
        stance=stance,
        triggers=triggers,
        key_phrases=key_phrases,
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "top_p": 0.9,
        },
    }

    try:
        res = _post_json(f"{OLLAMA_BASE}/api/generate", payload, timeout=90)
        raw = (res.get("response") or "").strip()

        if not raw.startswith("{"):
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw = raw[start:end + 1]

        data = json.loads(raw)

        user_summary = str(data.get("user_summary", "")).strip()[:1000]
        user_summary = _clean_summary_for_risk(
            summary=user_summary,
            risk_level_text=risk_level_text,
            prob_percent=prob_percent,
            stance=stance,
        )

        user_reasons = [str(x).strip()[:240] for x in data.get("user_reasons", []) if x][:3]
        user_guidance = str(data.get("user_guidance", safe_guidance)).strip()[:300]
        user_guidance = _guidance_for_current_risk(user_guidance, risk_level_text)
        final_explanation = str(data.get("final_explanation", "")).strip()[:1200]

        if not user_summary or len([s for s in user_summary.split(".") if s.strip()]) < 3:
            user_summary = _build_fallback_explanation(
                text=text,
                prob_pos=prob_pos,
                risk_band=forced_risk_band,
                stance=stance,
                triggers=triggers,
                key_phrases=key_phrases,
                guidance=safe_guidance,
            )

        if not final_explanation:
            final_explanation = user_summary

        return {
            "user_summary": user_summary,
            "user_reasons": user_reasons or [t.get("explanation", "") for t in triggers[:2] if t.get("explanation")],
            "user_guidance": user_guidance,
            "final_explanation": final_explanation,
            "signals": signals,
            "triggers": triggers,
            "key_phrases": key_phrases,
        }

    except Exception as e:
        print(f"⚠️ LLM explanation failed, using detailed fallback: {e}")

        user_summary = _build_fallback_explanation(
            text=text,
            prob_pos=prob_pos,
            risk_band=forced_risk_band,
            stance=stance,
            triggers=triggers,
            key_phrases=key_phrases,
            guidance=safe_guidance,
        )

        return {
            "user_summary": user_summary,
            "user_reasons": [t.get("explanation", "") for t in triggers[:2] if t.get("explanation")],
            "user_guidance": safe_guidance,
            "final_explanation": user_summary,
            "signals": signals,
            "triggers": triggers,
            "key_phrases": key_phrases,
        }


def _build_fallback_explanation(
    text: str,
    prob_pos: float,
    risk_band: str,
    stance: str,
    triggers: List[Dict],
    key_phrases: List[Dict],
    guidance: str,
) -> str:
    prob_percent = int(round(prob_pos * 100))
    risk_level = _risk_level_from_prob(prob_pos)

    words = text.split()
    topic = (" ".join(words[:12]) + "...") if len(words) > 12 else text

    phrase_detail = ""
    if key_phrases:
        phrases = [f"\"{p['phrase']}\"" for p in key_phrases[:2] if isinstance(p, dict) and p.get("phrase")]
        if phrases:
            phrase_detail = f" based on detected phrases like {', '.join(phrases)}"

    concern_sentence = _build_concern_sentence(
        risk_level=risk_level,
        stance=stance,
        triggers=triggers,
        key_phrases=key_phrases,
    )

    implication_sentence = _build_implication_sentence(
        risk_level=risk_level,
        stance=stance,
        phrase_detail=phrase_detail if risk_level in {"medium", "high"} else "",
    )

    clean_guidance = _guidance_for_current_risk(guidance, risk_level)
    if not clean_guidance:
        clean_guidance = _default_guidance_for_risk(risk_level)

    if not clean_guidance.endswith("."):
        clean_guidance = clean_guidance.rstrip() + "."

    sentences = [
        f"The text reports on {topic}.",
        concern_sentence,
        f"The model outputs indicate a {risk_level} risk of misinformation, with an estimated probability of {prob_percent}%.",
        implication_sentence,
        f"As such, it is essential to {clean_guidance}",
    ]

    return " ".join(sentences)


def _build_analyst_prompt(text: str, verdict: str, risk_band: str, prob_pos: float, stance: str = "neutral") -> str:
    return f"""
You are an OFFLINE analyst module for a misinformation-risk detection system.
You do NOT have internet access and MUST NOT claim you verified real-world facts.

TASK: Generate an analyst report about engagement triggers and spread dynamics.

STRICT RULES:
- Output ONLY valid JSON.
- No markdown. No extra keys. No trailing commentary.
- Do NOT invent real-world facts.
- Use neutral language - don't say "exploits" or "manipulates"

CONTEXT: This content is {stance}.

INPUT_TEXT:
{text}

MODEL_OUTPUT:
- verdict: {verdict}
- risk_band: {risk_band}
- prob_misinformation: {prob_pos:.6f}

Return JSON matching EXACTLY this schema:
{{
  "triggers": [
    {{
      "name": "Trigger Name",
      "score": 0.0,
      "explanation": "1-2 sentences describing the engagement cue"
    }}
  ],
  "propagation_dynamics": {{
    "infection_rate": "string (e.g., Rapid/Moderate/Slow)",
    "saturation_point": "string",
    "estimated_audience_reach": "string",
    "target_demographic": "string"
  }},
  "human_susceptibility_logic": "string (explain why people might engage with this)",
  "algorithmic_advantage": "string (explain how AI detects patterns)",
  "note": "string short disclaimer"
}}

CONSTRAINTS:
- Provide exactly 3 triggers.
- trigger.score must be in [0, 1].
- For fact-checking content, use neutral language about engagement.
"""


def _normalize_triggers(triggers: List[Dict], stance: str = "neutral") -> List[Dict]:
    cleaned = []
    seen = set()

    for t in (triggers or [])[:3]:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name", ""))[:80]
        score = _clamp01(t.get("score", 0.0))
        explanation = str(t.get("explanation", ""))[:500]

        if stance == "debunking":
            explanation = explanation.replace("exploit", "engage")
            explanation = explanation.replace("manipulate", "attract attention")
            explanation = explanation.replace("susceptible", "engaged")

        if name and explanation and name.lower() not in seen:
            seen.add(name.lower())
            cleaned.append({"name": name, "score": score, "explanation": explanation})

    if stance == "debunking":
        fallback_pool = [
            ("Topic Engagement", 0.45, "Health topics naturally attract attention and discussion online."),
            ("Source Credibility", 0.35, "Mentioning fact-checkers can increase trust."),
            ("Platform Mentions", 0.30, "References to platforms indicate where discussions are happening."),
        ]
    elif stance == "spreading":
        fallback_pool = [
            ("Emotional Appeal", 0.70, "Uses emotional language to provoke reaction."),
            ("Conspiracy Framing", 0.65, "Frames information as suppressed by authorities."),
            ("Urgency Cues", 0.60, "Creates time pressure to encourage sharing."),
        ]
    else:
        fallback_pool = [
            ("Emotional Engagement", 0.45, "Content that evokes emotion tends to attract more attention."),
            ("Social Proof", 0.35, "Mentioning widely shared claims can increase engagement."),
            ("Novelty", 0.30, "Unusual concepts may pique curiosity and encourage sharing."),
        ]

    while len(cleaned) < 3:
        name, score, exp = fallback_pool[len(cleaned)]
        if name.lower() not in seen:
            seen.add(name.lower())
            cleaned.append({"name": name, "score": score, "explanation": exp})

    return cleaned


def generate_analyst(
    text: str,
    verdict: str,
    risk_band: str,
    prob_pos: float,
    stance: str = "neutral",
) -> Dict[str, Any]:
    prompt = _build_analyst_prompt(
        text=text,
        verdict=verdict,
        risk_band=risk_band,
        prob_pos=prob_pos,
        stance=stance,
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.35, "top_p": 0.9},
    }

    last_err = None

    for attempt in range(2):
        try:
            if attempt == 1:
                payload["options"]["temperature"] = 0.2
                payload["prompt"] = prompt + "\n\nREMINDER: OUTPUT JSON ONLY. NO EXTRA WORDS."

            res = _post_json(f"{OLLAMA_BASE}/api/generate", payload, timeout=90)
            raw = (res.get("response") or "").strip()

            if not raw.startswith("{"):
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1 and end > start:
                    raw = raw[start:end + 1]

            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Ollama returned non-object JSON")

            triggers = _normalize_triggers(data.get("triggers", []), stance)

            pdyn = data.get("propagation_dynamics", {}) or {}
            propagation_dynamics = {
                "infection_rate": str(pdyn.get("infection_rate", "Moderate")),
                "saturation_point": str(pdyn.get("saturation_point", "Hours to days")),
                "estimated_audience_reach": str(pdyn.get("estimated_audience_reach", "Wide potential reach")),
                "target_demographic": str(pdyn.get("target_demographic", "General audience")),
            }

            human = str(data.get("human_susceptibility_logic", "")).strip()
            algo = str(data.get("algorithmic_advantage", "")).strip()
            note = str(data.get("note", "")).strip()

            if not human:
                human = "Content that evokes curiosity or addresses common concerns tends to attract engagement."
            if not algo:
                algo = "The system analyses linguistic patterns to identify content characteristics."

            return {
                "triggers": triggers,
                "propagation_dynamics": propagation_dynamics,
                "human_susceptibility_logic": human,
                "algorithmic_advantage": algo,
                "note": note or "Analysis based on linguistic patterns.",
            }

        except Exception as e:
            last_err = e
            print(f"⚠️ Analyst generation attempt {attempt + 1} failed: {e}")

    print(f"⚠️ Using final fallback for analyst: {last_err}")
    return {
        "triggers": _normalize_triggers([], stance),
        "propagation_dynamics": {
            "infection_rate": "Moderate",
            "saturation_point": "Hours to days",
            "estimated_audience_reach": "Variable based on engagement",
            "target_demographic": "General audience",
        },
        "human_susceptibility_logic": "Content that evokes curiosity or addresses common concerns tends to attract engagement.",
        "algorithmic_advantage": "The system analyses linguistic patterns to identify content characteristics.",
        "note": "Analysis based on linguistic patterns.",
    }