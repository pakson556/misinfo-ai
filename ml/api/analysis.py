"""
Rule-based behavioural analysis helpers used as safe fallback for analyst output.
Uses neutral, academically defensible language with stance awareness.
"""

from typing import List, Dict, Any
import re


def build_trigger_breakdown(text: str, stance: str = "neutral") -> List[Dict[str, Any]]:
    """
    Build trigger breakdown with stance-appropriate language.
    """
    t = (text or "").lower()
    triggers = []

    # Sharing prompts
    if any(x in t for x in ["share", "retweet", "forward", "spread", "pass"]):
        if stance == "debunking":
            explanation = "Mentions sharing - fact-checks often encourage spreading accurate information."
        else:
            explanation = "Contains language that encourages sharing."
        triggers.append({
            "name": "Sharing Cues",
            "score": 0.7,
            "explanation": explanation
        })

    # Urgency cues
    if any(x in t for x in ["breaking", "urgent", "just confirmed", "alert", "right now", "immediately"]):
        if stance == "debunking":
            explanation = "Timely topic that may attract attention."
        else:
            explanation = "Urgency cues may encourage timely engagement."
        triggers.append({
            "name": "Timeliness",
            "score": 0.6,
            "explanation": explanation
        })

    # Platform mentions (TikTok, YouTube, etc.)
    if any(x in t for x in ["tiktok", "youtube", "viral", "social media", "instagram", "facebook"]):
        triggers.append({
            "name": "Platform Mentions",
            "score": 0.5,
            "explanation": "References to social platforms indicate where this topic is circulating."
        })

    # Health topics
    if any(x in t for x in ["weight loss", "diet", "health", "vaccine", "salt", "cure", "treatment"]):
        if stance == "debunking":
            explanation = "Health-related content often attracts attention as people seek information."
        else:
            explanation = "Health topics naturally generate interest and discussion."
        triggers.append({
            "name": "Health Topic",
            "score": 0.45,
            "explanation": explanation
        })

    # AI/Technology topics
    if any(x in t for x in ["ai", "artificial intelligence", "ai-generated", "fake", "deepfake"]):
        triggers.append({
            "name": "Technology Topic",
            "score": 0.5,
            "explanation": "AI and technology topics generate curiosity and discussion."
        })

    # Celebrity/Landmark events
    if any(x in t for x in ["hollywood", "celebrity", "famous", "landmark"]):
        triggers.append({
            "name": "Cultural Reference",
            "score": 0.5,
            "explanation": "References to well-known places or people can attract attention."
        })

    # Fact-checker mentions
    if any(x in t for x in ["snopes", "fact-check", "expert", "debunked", "fact check"]):
        triggers.append({
            "name": "Source Credibility",
            "score": 0.4,
            "explanation": "Mentions credible sources that can verify information."
        })

    # Emotional markers
    excl_count = t.count("!")
    ques_count = t.count("?")
    if excl_count + ques_count > 3:
        if stance == "debunking":
            explanation = "Emphatic language may be used to highlight important points."
        else:
            explanation = "Emphatic punctuation may indicate heightened tone."
        triggers.append({
            "name": "Emphatic Language",
            "score": 0.4,
            "explanation": explanation
        })
    
    # Emotional words
    emotional_words = ["panic", "fear", "shocking", "outrage", "scared", "terrified", "horrified", "amazing", "incredible"]
    found_emotional = [word for word in emotional_words if word in t]
    if found_emotional:
        triggers.append({
            "name": "Emotional Language",
            "score": 0.5,
            "explanation": f"Words like '{found_emotional[0]}' may evoke emotional responses."
        })
    
    # Numbers/statistics
    if re.search(r'\d+%|\d+ percent|\d+ out of \d+|\d+ million|\d+ people', t):
        if stance == "debunking":
            explanation = "References specific data that can be verified."
        else:
            explanation = "Uses numbers that may create impression of precision."
        triggers.append({
            "name": "Quantitative Claims",
            "score": 0.4,
            "explanation": explanation
        })

    # Novelty/unusual concepts
    if any(x in t for x in ["pink salt", "unusual", "strange", "weird", "non-existent"]):
        triggers.append({
            "name": "Novelty",
            "score": 0.3,
            "explanation": "Unusual concepts may pique curiosity."
        })

    # Crime/violence references
    if any(x in t for x in ["shooting", "crime", "violence", "attack", "stabbings"]):
        triggers.append({
            "name": "Sensitive Topic",
            "score": 0.5,
            "explanation": "References to sensitive events may attract attention."
        })

    # Vaccine safety discussion (NEW)
    if "vaccine" in t or "vaccines" in t or "vax" in t:
        if any(x in t for x in ["safe", "safety", "testing", "years", "approved", "doctor"]):
            triggers.append({
                "name": "Vaccine Safety Information",
                "score": 0.3,
                "explanation": "Discusses vaccine safety protocols and testing procedures."
            })
        elif any(x in t for x in ["big pharma", "rushed", "lab rats", "zero testing", "do your own research"]):
            triggers.append({
                "name": "Vaccine Skepticism",
                "score": 0.7,
                "explanation": "Expresses concerns about vaccine development and testing."
            })
        elif any(x in t for x in ["side effects", "rare", "serious reactions"]):
            triggers.append({
                "name": "Side Effect Discussion",
                "score": 0.4,
                "explanation": "Discusses potential vaccine side effects and their frequency."
            })

    # Climate change discussion (NEW)
    if "climate" in t or "weather" in t or "global warming" in t:
        if any(x in t for x in ["hoax", "propaganda", "fool", "raise taxes", "control your life"]):
            triggers.append({
                "name": "Climate Denial Language",
                "score": 0.8,
                "explanation": "Uses language that dismisses climate science."
            })
        elif any(x in t for x in ["always changed", "nothing unusual", "normal cycle"]):
            triggers.append({
                "name": "Climate Minimization",
                "score": 0.6,
                "explanation": "Suggests current climate patterns are not unusual."
            })
        else:
            triggers.append({
                "name": "Climate Discussion",
                "score": 0.3,
                "explanation": "General discussion about climate or weather patterns."
            })

    # Conspiracy language (NEW)
    conspiracy_terms = ["they don't want", "cover up", "hidden truth", "what they won't tell", "mainstream media won't"]
    if any(term in t for term in conspiracy_terms):
        triggers.append({
            "name": "Conspiracy Framing",
            "score": 0.8,
            "explanation": "Frames information as suppressed by authorities."
        })

    # Authority distrust (NEW)
    if any(x in t for x in ["big pharma", "government", "media", "they"]):
        if any(x in t for x in ["lying", "fool", "control", "propaganda"]):
            triggers.append({
                "name": "Authority Distrust",
                "score": 0.7,
                "explanation": "Expresses distrust toward institutions or authorities."
            })

    # Call to action (NEW)
    if "do your own research" in t:
        triggers.append({
            "name": "Research Prompt",
            "score": 0.5,
            "explanation": "Encourages independent research, which may lead to unverified sources."
        })

    if not triggers:
        triggers.append({
            "name": "Neutral Presentation",
            "score": 0.2,
            "explanation": "Text lacks strong emotional or urgency cues."
        })

    return triggers


def build_propagation_dynamics(risk_band: str, stance: str = "neutral") -> Dict[str, Any]:
    """
    Estimate propagation potential with stance-appropriate descriptions.
    """
    if stance == "debunking":
        # Fact-checking content spreads differently
        return {
            "infection_rate": "Moderate",
            "saturation_point": "Days",
            "estimated_audience_reach": "May reach audiences interested in the topic",
            "target_demographic": "People seeking accurate information",
        }
    elif stance == "credible":
        return {
            "infection_rate": "Slow to Moderate",
            "saturation_point": "Days to weeks",
            "estimated_audience_reach": "Limited to those seeking official information",
            "target_demographic": "News followers and fact-checkers",
        }
    elif stance == "satire":
        return {
            "infection_rate": "Moderate",
            "saturation_point": "Days",
            "estimated_audience_reach": "May spread among humor-focused audiences",
            "target_demographic": "People who appreciate satire",
        }
    elif risk_band == "HIGH":
        return {
            "infection_rate": "Rapid",
            "saturation_point": "Hours",
            "estimated_audience_reach": "Broad potential reach",
            "target_demographic": "General audience",
        }
    elif risk_band == "MEDIUM":
        return {
            "infection_rate": "Moderate",
            "saturation_point": "Days",
            "estimated_audience_reach": "Moderate potential reach",
            "target_demographic": "Engaged communities",
        }
    else:
        return {
            "infection_rate": "Low",
            "saturation_point": "Limited spread expected",
            "estimated_audience_reach": "Niche audiences",
            "target_demographic": "Specific interest groups",
        }


def build_susceptibility_logic(text: str, stance: str = "neutral") -> str:
    """
    Neutral explanation of why people might engage with content.
    """
    t = text.lower()
    
    if stance == "debunking":
        return (
            "People may seek out fact-checks when they encounter surprising claims online. "
            "Content that references popular platforms or events can attract attention "
            "from users who have seen the original misinformation."
        )
    elif stance == "credible":
        return (
            "Official sources and verified information tend to attract attention from "
            "people seeking accurate information about important topics."
        )
    elif stance == "satire":
        return (
            "Satirical content often engages people through humor and shared cultural "
            "references, though it may sometimes be taken out of context."
        )
    elif "vaccine" in t and "safe" in t:
        return (
            "People may engage with vaccine safety information when making personal "
            "health decisions or when encountering conflicting claims online."
        )
    elif "vaccine" in t and any(x in t for x in ["big pharma", "rushed", "lab rats"]):
        return (
            "Vaccine skepticism often spreads through concerns about safety and distrust "
            "of pharmaceutical companies, which can resonate with people who have health anxieties."
        )
    elif "climate" in t and any(x in t for x in ["hoax", "propaganda"]):
        return (
            "Climate denial content may appeal to people who are skeptical of government "
            "or scientific institutions, or who feel threatened by proposed policy changes."
        )
    elif "weight loss" in t or "diet" in t:
        return (
            "Health and weight loss topics naturally attract attention as people seek solutions. "
            "When such content goes viral on social platforms, it can reach many users quickly."
        )
    elif "ai" in t or "artificial intelligence" in t:
        return (
            "AI and technology topics generate curiosity as people try to understand "
            "emerging technologies and their implications."
        )
    elif "hollywood" in t or "celebrity" in t:
        return (
            "References to famous places or people tend to attract attention "
            "due to cultural familiarity and interest."
        )
    elif "shooting" in t or "crime" in t or "stabbings" in t:
        return (
            "Sensitive events may attract attention as people seek to understand "
            "what happened and its implications. False claims often spread rapidly during such events."
        )
    elif "share" in t or "spread" in t:
        return (
            "Content that includes sharing cues may spread more readily, as these prompts can "
            "trigger sharing behaviors."
        )
    elif "breaking" in t or "urgent" in t:
        return (
            "Time-sensitive language can create interest and encourage timely engagement with content."
        )
    else:
        return (
            "Content that evokes curiosity or addresses common concerns tends to attract engagement."
        )


def build_algorithmic_advantage(text: str, stance: str = "neutral") -> str:
    """
    Neutral explanation of how AI detects patterns with specific examples from the text.
    """
    t = text.lower()
    
    # Detect specific patterns in the text
    patterns = []
    
    # AI/Tech patterns
    if "ai" in t or "artificial intelligence" in t or "ai-generated" in t:
        patterns.append("discussions of AI-generated content")
    
    # Event references
    if "hollywood sign" in t:
        patterns.append("references to landmark events")
    elif "hollywood" in t:
        patterns.append("references to cultural landmarks")
    
    # Emotional language
    if "panic" in t:
        patterns.append("emotionally charged language ('panic')")
    elif "widespread" in t:
        patterns.append("scale-related language ('widespread')")
    
    # Sensitive events
    if "shooting" in t or "stabbings" in t:
        patterns.append("references to sensitive events")
    
    # Fake/manipulated content
    if "fake" in t or "non-existent" in t:
        patterns.append("discussions of fabricated content")
    
    # Vaccine-related patterns (NEW)
    if "vaccine" in t:
        if "safe" in t or "testing" in t or "years" in t:
            patterns.append("vaccine safety information")
        elif "big pharma" in t:
            patterns.append("pharmaceutical industry criticism")
        elif "rushed" in t:
            patterns.append("concerns about vaccine development speed")
        elif "lab rats" in t:
            patterns.append("dehumanizing language about vaccine recipients")
    
    # Climate-related patterns (NEW)
    if "climate" in t:
        if "hoax" in t or "propaganda" in t:
            patterns.append("climate denial framing")
        elif "always changed" in t:
            patterns.append("climate minimization arguments")
    
    # Conspiracy patterns (NEW)
    if any(x in t for x in ["they don't want", "cover up", "hidden truth"]):
        patterns.append("conspiracy framing")
    
    # Authority distrust (NEW)
    if "fool you" in t or "don't let them" in t:
        patterns.append("warnings about being misled")
    
    # Year references (future/past)
    if re.search(r'202\d', t):
        patterns.append("future/past year references")
    
    if stance == "debunking":
        if patterns:
            pattern_list = ", ".join(patterns[:-1]) + (" and " + patterns[-1] if len(patterns) > 1 else patterns[0])
            return (
                f"The system detected language patterns commonly found in fact-checking content: "
                f"{pattern_list}. These patterns help identify how information might spread online."
            )
        else:
            return (
                "The system analyzed the text's structure and identified it as fact-checking content "
                "based on the presence of debunking language and credible source mentions."
            )
    elif stance == "spreading":
        if patterns:
            pattern_list = ", ".join(patterns[:-1]) + (" and " + patterns[-1] if len(patterns) > 1 else patterns[0])
            return (
                f"The system detected {pattern_list}, which are patterns commonly associated with "
                f"content that spreads rapidly online. These cues help assess potential misinformation risk."
            )
        else:
            return (
                "The system identified language patterns consistent with content that often spreads "
                "in online communities, including emotional appeals and calls to action."
            )
    else:
        if patterns:
            pattern_list = ", ".join(patterns[:-1]) + (" and " + patterns[-1] if len(patterns) > 1 else patterns[0])
            return (
                f"The system detected {pattern_list}, which are patterns commonly associated with "
                f"content that attracts attention online. These cues help assess potential spread dynamics."
            )
        else:
            return (
                "The system analyzes linguistic patterns to identify content characteristics "
                "associated with different types of online information."
            )