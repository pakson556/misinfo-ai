"""
Stance detection module to identify whether text is debunking,
warning about, or spreading misinformation.
Uses neutral, academically defensible language.
"""

import re
from typing import Dict, List, Tuple, Literal
import math

# Comprehensive pattern lists with improved detection
DEBUNK_PATTERNS = [
    # Direct refutation
    r"no evidence",
    r"found no",
    r"does not show",
    r"not true",
    r"is false",
    r"are false",
    r"was false",
    r"debunked",
    r"debunks",
    r"refutes",
    r"refuted",
    r"disproves",
    r"disproved",
    r"counter(s|ed)?",
    r"actually",
    
    # Fact-checking language
    r"fact[ -]?check",
    r"factcheck",
    r"contrary to",
    r"in reality",
    r"the truth is",
    r"according to facts",
    r"based on evidence",
    
    # Scientific refutation
    r"study found no",
    r"research shows no",
    r"data indicates no",
    r"no significant",
    r"no correlation",
    r"no link",
    r"found no evidence",
    
    # Clarifying misinformation
    r"misleading",
    r"misinformation",
    r"false information",
    r"fake news",
    r"hoax",
    r"myth",
    r"conspiracy theory",
    
    # Source credibility
    r"snopes",
    r"fact-checkers?",
    r"experts say",
    
    # Pro-vaccine fact-checking (NEW)
    r"years of safety testing",
    r"talk to a real doctor",
    r"side effects.*rare",
    r"vaccines?.*safe",
    r"approved.*public use",
    r"serious reactions.*extremely rare",
    r"go through.*testing",
]

WARNING_PATTERNS = [
    # Verification advice
    r"be cautious",
    r"be careful",
    r"verify",
    r"check before",
    r"don't share",
    r"do not share",
    r"think twice",
    r"look into",
    r"investigate",
    
    # Alert language
    r"be aware",
    r"warning",
    r"alert",
    r"caution",
    r"attention",
    
    # Sourcing advice
    r"check sources",
    r"verify sources",
    r"reputable sources",
    r"official sources",
    r"primary sources",
]

SPREADING_PATTERNS = [
    # Sharing prompts
    r"share this",
    r"spread the word",
    r"pass this on",
    r"forward to",
    r"tell everyone",
    r"share widely",
    r"go viral",
    r"share before",
    
    # Conspiracy language
    r"they don't want you to know",
    r"cover[ -]?up",
    r"they're hiding",
    r"hidden truth",
    r"what they won't tell",
    r"mainstream media won't",
    r"wake up",
    r"sheeple",
    r"deep state",
    
    # Urgency
    r"urgent",
    r"immediately",
    r"right now",
    r"before it's too late",
    r"act now",
    
    # Emotional manipulation
    r"you won't believe",
    r"incredible",
    r"shocking",
    r"mind[ -]?blowing",
    r"unbelievable",
    
    # False authority
    r"100% confirmed",
    r"insiders?",
    r"confirmed by insiders",
    r"trust me",
    r"i know for a fact",
    
    # Media distrust
    r"media covers? up",
    r"mainstream media won't",
    r"they don't want.*know",
    
    # Multiple exclamation marks
    r"!!!+",
    
    # Vaccine skepticism (NEW)
    r"big pharma",
    r"rushed.*vaccines?",
    r"zero.*testing",
    r"lab rats",
    r"do your own research",
    r"no one knows",
    r"what will happen",
    r"in a year or two",
    
    # Climate denial (NEW)
    r"climate change.*hoax",
    r"propaganda",
    r"fool you",
    r"raise taxes",
    r"control your life",
    r"nothing unusual",
    r"weather has always changed",
    r"don't let them fool",
]

# Satire patterns
SATIRE_PATTERNS = [
    r"april fools?",
    r"satire",
    r"made-?up",
    r"not real",
    r"joke",
    r"just kidding",
    r"fictional",
    r"institute of made-?up",
    r"imaginary",
    r"pretend",
]

# Credible source patterns
CREDIBLE_PATTERNS = [
    r"officials? confirm",
    r"according to.*committee",
    r"organizing committee",
    r"official sources?",
    r"confirmed by",
    r"announced by",
    r"statement from",
    r"press release",
    r"government official",
]

# Weighting for different pattern types
PATTERN_WEIGHTS = {
    "debunk": 1.5,      # Strong signal for debunking
    "warning": 1.0,     # Moderate signal
    "spreading": 2.5,   # Strong signal for spreading
    "satire": 2.0,      # Strong signal for satire
    "credible": 1.5,    # Strong signal for credible sources
}

def detect_stance(text: str) -> Dict[str, any]:
    """
    Detect the stance of the text and return detailed analysis.
    
    Returns:
        Dict with keys:
        - stance: "debunking", "warning", "neutral", "spreading", "satire", "credible"
        - confidence: float (0-1)
        - scores: Dict with individual category scores
        - matched_patterns: List of matched patterns
        - debunk_confidence: float (0-1) confidence in debunking detection
    """
    text_lower = text.lower()
    
    # Count matches in each category
    debunk_matches = []
    warning_matches = []
    spreading_matches = []
    satire_matches = []
    credible_matches = []
    
    for pattern in DEBUNK_PATTERNS:
        if re.search(pattern, text_lower):
            debunk_matches.append(pattern)
    
    for pattern in WARNING_PATTERNS:
        if re.search(pattern, text_lower):
            warning_matches.append(pattern)
    
    for pattern in SPREADING_PATTERNS:
        if re.search(pattern, text_lower):
            spreading_matches.append(pattern)
    
    for pattern in SATIRE_PATTERNS:
        if re.search(pattern, text_lower):
            satire_matches.append(pattern)
    
    for pattern in CREDIBLE_PATTERNS:
        if re.search(pattern, text_lower):
            credible_matches.append(pattern)
    
    # Calculate weighted scores
    debunk_score = len(debunk_matches) * PATTERN_WEIGHTS["debunk"]
    warning_score = len(warning_matches) * PATTERN_WEIGHTS["warning"]
    spreading_score = len(spreading_matches) * PATTERN_WEIGHTS["spreading"]
    satire_score = len(satire_matches) * PATTERN_WEIGHTS["satire"]
    credible_score = len(credible_matches) * PATTERN_WEIGHTS["credible"]
    
    # Normalize by text length to avoid bias toward long texts
    word_count = len(text_lower.split())
    if word_count > 0:
        normalization_factor = math.sqrt(word_count) / 10  # Gentle normalization
        debunk_score = debunk_score / max(1, normalization_factor)
        warning_score = warning_score / max(1, normalization_factor)
        spreading_score = spreading_score / max(1, normalization_factor)
        satire_score = satire_score / max(1, normalization_factor)
        credible_score = credible_score / max(1, normalization_factor)
    
    scores = {
        "debunk": debunk_score,
        "warning": warning_score,
        "spreading": spreading_score,
        "satire": satire_score,
        "credible": credible_score,
        "neutral": 1.0  # Base neutral score
    }
    
    # Determine stance with confidence - check satire and credible first
    if satire_score > 1.5 and satire_score > spreading_score and satire_score > debunk_score:
        stance = "satire"
        confidence = min(1.0, satire_score / 3)
        debunk_confidence = 0.0
    elif credible_score > 1.5 and credible_score > spreading_score:
        stance = "credible"
        confidence = min(1.0, credible_score / 2.5)
        debunk_confidence = 0.3
    elif debunk_score > warning_score and debunk_score > spreading_score and debunk_score > 0.8:
        stance = "debunking"
        confidence = min(1.0, debunk_score / 3)
        debunk_confidence = confidence
    elif spreading_score > warning_score and spreading_score > debunk_score and spreading_score > 0.6:
        stance = "spreading"
        confidence = min(1.0, spreading_score / 4)
        debunk_confidence = 0.0
    elif warning_score > 0.8:
        stance = "warning"
        confidence = min(1.0, warning_score / 2.5)
        debunk_confidence = 0.2
    else:
        stance = "neutral"
        confidence = 0.7 if (debunk_score + warning_score + spreading_score) < 0.8 else 0.5
        debunk_confidence = 0.1
    
    return {
        "stance": stance,
        "confidence": confidence,
        "debunk_confidence": debunk_confidence,
        "scores": scores,
        "matched_patterns": {
            "debunk": debunk_matches[:5],
            "warning": warning_matches[:5],
            "spreading": spreading_matches[:5],
            "satire": satire_matches[:5],
            "credible": credible_matches[:5],
        }
    }


def adjust_risk_by_stance(base_prob: float, stance_data: Dict[str, any]) -> float:
    """
    Adjust misinformation probability based on stance.
    
    Args:
        base_prob: Original probability from model ensemble
        stance_data: Output from detect_stance()
    
    Returns:
        Adjusted probability
    """
    stance = stance_data["stance"]
    confidence = stance_data["confidence"]
    debunk_confidence = stance_data.get("debunk_confidence", 0.0)
    
    # Special handling for satire - drastically reduce risk
    if stance == "satire":
        return base_prob * 0.1  # 90% reduction
    
    # Special handling for credible sources - significantly reduce risk
    if stance == "credible":
        return base_prob * 0.3  # 70% reduction
    
    # Adjustment factors - more aggressive for spreading content
    if stance == "debunking":
        # Drastically reduce for debunking content
        factor = 0.15 + (0.15 * (1 - debunk_confidence))  # 0.15 to 0.3
        return base_prob * factor
    
    elif stance == "warning":
        # Moderately reduce for warning content
        factor = 0.4 + (0.2 * (1 - confidence))  # 0.4 to 0.6
        return base_prob * factor
    
    elif stance == "spreading":
        # Significantly increase for spreading content - UPDATED
        factor = 1.6 + (0.5 * confidence)  # Increased from 1.4 to 1.6
        return min(0.98, base_prob * factor)  # Cap at 0.98
    
    else:  # neutral
        # Slight adjustment based on other signals
        if base_prob > 0.6:
            # High probability already, likely spreading
            return min(0.95, base_prob * 1.2)
        else:
            return base_prob


def get_stance_explanation(stance_data: Dict[str, any]) -> str:
    """
    Generate user-friendly explanation of stance detection.
    """
    stance = stance_data["stance"]
    matches = stance_data["matched_patterns"]
    confidence = stance_data["confidence"]
    
    explanations = {
        "debunking": f"This text contains language consistent with fact-checking or debunking content (confidence: {confidence:.0%}). It appears to be actively countering potential misinformation.",
        "warning": f"This text contains language consistent with warning readers about potential misinformation (confidence: {confidence:.0%}). It advises verification rather than sharing.",
        "spreading": f"This text contains language patterns associated with spreading unverified claims (confidence: {confidence:.0%}), including sharing prompts and urgency cues.",
        "neutral": "This text does not show strong signals of either debunking or spreading misinformation.",
        "satire": f"This text contains clear markers of satire or parody (confidence: {confidence:.0%}), such as 'April Fools' or made-up references.",
        "credible": f"This text cites official sources and contains verifiable information (confidence: {confidence:.0%}).",
    }
    
    base = explanations.get(stance, "")
    
    # Add examples if available and confidence is high enough
    if confidence > 0.3:
        examples = []
        for category, patterns in matches.items():
            if patterns and (category == stance or stance == "neutral" and patterns):
                example = patterns[0] if patterns else None
                if example:
                    # Clean up the pattern for display
                    clean_example = example.replace(r"\s*", " ").replace(r"\?", "?").replace(r"\.", ".")
                    examples.append(f"'{clean_example}'")
        
        if examples:
            base += f" Detected patterns: {', '.join(examples[:2])}."
    
    return base