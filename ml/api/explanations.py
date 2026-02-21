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
    """
    Build prompt for explanation generation with stance awareness and triggers.
    Designed to generate longer, detailed explanations (4-5 sentences).
    """

    # Format triggers for prompt
    trigger_text = ""
    if triggers:
        trigger_text = "Detected patterns:\n"
        for t in triggers[:3]:
            trigger_text += (
                f"- {t.get('name', 'Unknown')}: {int(t.get('score', 0)*100)}% - "
                f"{t.get('explanation', '')}\n"
            )

    # Format key phrases
    key_phrases_text = ""
    if key_phrases:
        phrase_words = [f"\"{p['phrase']}\"" for p in key_phrases[:3]]
        key_phrases_text = f"Key phrases detected: {', '.join(phrase_words)}."

    # Adjust prompt based on stance
    if stance == "debunking":
        stance_context = "This is fact-checking or educational content that discusses misinformation rather than spreading it."
    elif stance == "spreading":
        stance_context = "This content shows patterns of spreading unverified claims."
    elif stance == "warning":
        stance_context = "This content warns about potential misinformation."
    elif stance == "satire":
        stance_context = "This is satirical or parody content."
    elif stance == "credible":
        stance_context = "This content cites official sources."
    else:
        stance_context = "This content appears neutral in tone."

    # Use ROUND to match frontend display (Math.round(prob*100))
    prob_percent = int(round(prob_pos * 100))

    return f"""
You are an OFFLINE explanation module for a misinformation-risk detection system.
You do NOT have internet access and MUST NOT claim you verified real-world facts.

Your job: Write a DETAILED, "report-style" explanation based ONLY on the input text and model outputs.
The explanation MUST be 4-5 sentences long - structured exactly like the example below.

Return ONLY VALID JSON. No markdown. No extra text.

CONTEXT: {stance_context}

INPUT_TEXT:
{text}

MODEL_OUTPUT:
- verdict: {verdict}
- risk_band: {risk_band}
- prob_misinformation: {prob_pos:.6f} ({prob_percent}%)
- prob_non_misinformation: {prob_neg:.6f}
- spread_potential: {early_prob if early_prob else 'null'}
- {key_phrases_text}

{trigger_text}

Return JSON exactly matching this schema:
{{
  "user_summary": "A DETAILED paragraph (4-5 sentences) that follows this exact format: Sentence 1: 'The text reports on [main topic/claim].' Sentence 2: 'However, [specific concern about credibility].' Sentence 3: 'The model outputs indicate a [low/medium/high] risk of misinformation, with an estimated probability of [X]%.' Sentence 4: 'This suggests that [explain what this means].' Sentence 5: 'As such, it is essential to [guidance].'",
  "user_reasons": ["2-3 bullet points explaining the main signals"],
  "user_guidance": "{guidance}",
  "final_explanation": "The same as user_summary (for backward compatibility)",
  "signals": {{}}
}}

EXAMPLE OF CORRECT FORMAT:
"The text reports on unconfirmed information regarding the prime minister's resignation, citing a secret meeting and internal party conflict. However, the lack of an official statement and unspecified sources raises concerns about the credibility of these claims. The model outputs indicate a high risk of misinformation, with an estimated probability of 92%. This suggests that the report may be based on speculation or biased interpretations rather than verifiable evidence. As such, it is essential to exercise caution when engaging with this content and seek primary evidence from official sources before sharing or accepting these claims."

CRITICAL FORMATTING RULES:
- The explanation MUST be 4-5 sentences long
- Follow the exact structure: topic sentence, concern sentence, probability sentence, implication sentence, guidance sentence
- Use professional, neutral language
- For {prob_percent}% probability, use appropriate risk level
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
    """
    Generate user-friendly explanation using LLM with stance awareness and triggers.
    This version ensures consistency between risk level display and content analysis.
    """
    signals = signals or {}
    triggers = triggers or []
    key_phrases = key_phrases or []

    # Use ROUND to match frontend display (Math.round(prob*100))
    prob_percent = int(round(prob_pos * 100))

    # Determine risk level based on probability - MATCH FRONTEND THRESHOLDS
    if prob_percent >= 45:
        risk_level_text = "high"
    elif prob_percent >= 15:
        risk_level_text = "medium"
    else:
        risk_level_text = "low"

    forced_risk_band = risk_level_text.upper()

    prompt = _build_explanation_prompt(
        text=text,
        verdict=verdict,
        risk_band=forced_risk_band,
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        early_prob=early_prob,
        signals=signals,
        guidance=guidance,
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

        # Try to extract JSON if there's extra text
        if not raw.startswith("{"):
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw = raw[start:end + 1]

        data = json.loads(raw)

        user_summary = str(data.get("user_summary", ""))[:1000]

        # ENSURE the summary uses the correct risk level
        if "high risk" in user_summary.lower() and risk_level_text != "high":
            user_summary = re.sub(r"high risk", f"{risk_level_text} risk", user_summary, flags=re.IGNORECASE)
        elif "medium risk" in user_summary.lower() and risk_level_text != "medium":
            user_summary = re.sub(r"medium risk", f"{risk_level_text} risk", user_summary, flags=re.IGNORECASE)
        elif "low risk" in user_summary.lower() and risk_level_text != "low":
            user_summary = re.sub(r"low risk", f"{risk_level_text} risk", user_summary, flags=re.IGNORECASE)

        # Ensure probability is consistent.
        fixed = re.sub(
            r"(estimated probability of\s*)\d+%",
            rf"\g<1>{prob_percent}%",
            user_summary,
            flags=re.IGNORECASE,
            count=1,
        )
        if fixed != user_summary:
            user_summary = fixed
        else:
            # Fallback: replace first % we see
            matches = re.findall(r"(\d+)%", user_summary)
            if matches and int(matches[0]) != prob_percent:
                old_percent = matches[0]
                user_summary = user_summary.replace(f"{old_percent}%", f"{prob_percent}%", 1)

        user_reasons = [str(x).strip()[:240] for x in data.get("user_reasons", []) if x][:3]
        user_guidance = str(data.get("user_guidance", guidance))[:300]
        final_explanation = str(data.get("final_explanation", ""))[:1200]

        # If LLM failed or summary is too short, use fallback
        if not user_summary or len([s for s in user_summary.split(".") if s.strip()]) < 3:
            user_summary = _build_fallback_explanation(
                text, prob_pos, risk_band, stance, triggers, key_phrases, guidance
            )

        return {
            "user_summary": user_summary,
            "user_reasons": user_reasons or [t.get("explanation", "") for t in triggers[:2]],
            "user_guidance": user_guidance or guidance,
            "final_explanation": final_explanation or user_summary,
            "signals": signals,
            "triggers": triggers,
            "key_phrases": key_phrases,
        }

    except Exception as e:
        print(f"⚠️ LLM explanation failed, using detailed fallback: {e}")

        user_summary = _build_fallback_explanation(
            text, prob_pos, risk_band, stance, triggers, key_phrases, guidance
        )

        return {
            "user_summary": user_summary,
            "user_reasons": [t.get("explanation", "") for t in triggers[:2]],
            "user_guidance": guidance,
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
    """
    Build a detailed fallback explanation (4-5 sentences) matching the exact format.
    """
    # Use ROUND to match frontend display
    prob_percent = int(round(prob_pos * 100))

    # Determine risk level based on probability - MATCH FRONTEND THRESHOLDS
    if prob_percent >= 45:
        risk_level = "high"
    elif prob_percent >= 15:
        risk_level = "medium"
    else:
        risk_level = "low"

    words = text.split()
    topic = (" ".join(words[:8]) + "...") if len(words) > 8 else text

    concern = ""
    if triggers:
        trigger_names = [t.get("name", "") for t in triggers[:2] if t.get("name")]
        if trigger_names:
            concern = (
                f"citing {trigger_names[0].lower()}"
                if len(trigger_names) == 1
                else f"citing {trigger_names[0].lower()} and {trigger_names[1].lower()}"
            )

    phrase_detail = ""
    if key_phrases:
        phrases = [f"\"{p['phrase']}\"" for p in key_phrases[:2] if isinstance(p, dict) and p.get("phrase")]
        if phrases:
            phrase_detail = f" based on detected phrases like {', '.join(phrases)}"

    sentences = []
    sentences.append(f"The text reports on {topic}.")
    if concern:
        sentences.append(
            f"However, the pattern of language used, {concern}, raises concerns about the credibility of these claims."
        )
    else:
        sentences.append(
            "However, the lack of verifiable sources and specific details raises concerns about the credibility of these claims."
        )

    sentences.append(
        f"The model outputs indicate a {risk_level} risk of misinformation, with an estimated probability of {prob_percent}%."
    )

    if prob_percent >= 45:
        sentences.append(
            f"This suggests that the report may be based on unverified claims or biased interpretations rather than verifiable evidence{phrase_detail}."
        )
    elif prob_percent >= 15:
        sentences.append(
            f"This suggests that the content contains elements that could be either factual or misleading{phrase_detail}."
        )
    else:
        sentences.append(
            "This suggests that the content appears to be generally reliable, though it's always good practice to verify important claims."
        )

    clean_guidance = (guidance or "").strip()
    if not clean_guidance:
        clean_guidance = "verify key claims before sharing."

    # Ensure it ends nicely
    if not clean_guidance.endswith("."):
        clean_guidance = clean_guidance.rstrip() + "."

    sentences.append(f"As such, it is essential to {clean_guidance}")

    return " ".join(sentences)


def _build_analyst_prompt(text: str, verdict: str, risk_band: str, prob_pos: float, stance: str = "neutral") -> str:
    """
    Build prompt for analyst-style explanation with stance awareness.
    """
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
    """Clean and deduplicate triggers with stance-appropriate language"""
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

    # Ensure exactly 3 triggers with stance-appropriate fallbacks
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
    """
    Generate analyst-focused analysis using LLM with stance awareness.
    """
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
            print(f"⚠️ Analyst generation attempt {attempt+1} failed: {e}")

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
