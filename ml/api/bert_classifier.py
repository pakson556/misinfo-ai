"""
BERT-based classifier for context-aware misinformation detection.
This provides a second opinion that understands nuance better than pattern-matching.
"""

import re
from typing import Dict, List, Any, Optional
import numpy as np

# Try to import torch and transformers, but don't fail if not available
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
    print("✅ Transformers library available")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ Transformers/torch not available. BERT classifier will use fallback mode.")
    torch = None
    AutoTokenizer = None
    AutoModelForSequenceClassification = None

class BertMisinformationClassifier:
    def __init__(self, model_name="facebook/bart-large-mnli"):
        """
        Initialize with a zero-shot classifier that can understand context.
        Using BART trained on MNLI for natural language inference.
        """
        self.device = None
        self.tokenizer = None
        self.model = None
        self.model_name = model_name
        self.transformers_available = TRANSFORMERS_AVAILABLE
        
        if self.transformers_available:
            try:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                print(f"📊 BERT classifier using device: {self.device}")
                
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
                self.model.eval()
                print(f"✅ Loaded BERT model: {model_name}")
            except Exception as e:
                print(f"⚠️ Failed to load BERT model: {e}")
                self.transformers_available = False
        else:
            print("⚠️ BERT classifier running in fallback mode (rule-based)")
        
        # Cache for common patterns
        self.cache = {}
        
    def predict_stance(self, text: str) -> Dict[str, float]:
        """
        Predict whether text is supporting, refuting, or neutral toward a claim.
        This helps distinguish between spreading vs debunking.
        """
        if not self.transformers_available:
            # Fallback to simple rule-based detection
            return self._fallback_stance_detection(text)
        
        # Check cache first
        if text in self.cache:
            return self.cache[text]
        
        # Define hypotheses
        hypotheses = [
            "This text is spreading misinformation.",
            "This text is fact-checking or debunking misinformation.",
            "This text is neutral or educational.",
            "This text is satirical or parody.",
            "This text is promoting a conspiracy theory.",
            "This text is citing scientific evidence.",
            "This text is expressing a personal opinion.",
            "This text is reporting news factually.",
        ]
        
        scores = {}
        for hypothesis in hypotheses:
            try:
                # Prepare input
                inputs = self.tokenizer(
                    text,
                    hypothesis,
                    truncation=True,
                    padding=True,
                    max_length=512,
                    return_tensors="pt"
                ).to(self.device)
                
                # Get prediction
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    probs = torch.softmax(logits, dim=-1)
                    
                    # For MNLI, we want the entailment score (class 0)
                    # 0: entailment, 1: neutral, 2: contradiction
                    entailment_score = probs[0][0].item()
                    scores[hypothesis] = entailment_score
            except Exception as e:
                print(f"⚠️ Error predicting for hypothesis '{hypothesis}': {e}")
                scores[hypothesis] = 0.0
        
        # Normalize scores if any were successful
        if scores and any(scores.values()):
            total = sum(scores.values())
            if total > 0:
                scores = {k: v/total for k, v in scores.items()}
        
        self.cache[text] = scores
        return scores
    
    def _fallback_stance_detection(self, text: str) -> Dict[str, float]:
        """
        Simple rule-based fallback when transformers aren't available.
        """
        text_lower = text.lower()
        scores = {}
        
        # Check for fact-checking indicators
        fact_check_keywords = [
            "fact-check", "debunked", "misleading", "false claim",
            "no evidence", "actually", "in reality", "contrary to",
            "snopes", "fact check"
        ]
        fact_check_score = sum(1 for kw in fact_check_keywords if kw in text_lower) / len(fact_check_keywords)
        
        # Check for spreading indicators
        spreading_keywords = [
            "share this", "spread the word", "they don't want",
            "cover up", "hidden truth", "wake up", "conspiracy",
            "big pharma", "hoax", "propaganda"
        ]
        spreading_score = sum(1 for kw in spreading_keywords if kw in text_lower) / len(spreading_keywords)
        
        # Check for credible indicators
        credible_keywords = [
            "study", "research", "evidence", "data", "clinical trials",
            "scientists", "experts", "according to", "study shows",
            "research indicates"
        ]
        credible_score = sum(1 for kw in credible_keywords if kw in text_lower) / len(credible_keywords)
        
        # Check for satire indicators
        satire_keywords = ["april fools", "satire", "joke", "parody", "made-up", "not real"]
        satire_score = sum(1 for kw in satire_keywords if kw in text_lower) / len(satire_keywords)
        
        # Add small base scores
        scores = {
            "This text is fact-checking or debunking misinformation.": fact_check_score + 0.1,
            "This text is spreading misinformation.": spreading_score + 0.1,
            "This text is citing scientific evidence.": credible_score + 0.1,
            "This text is satirical or parody.": satire_score + 0.1,
            "This text is neutral or educational.": 0.2,
        }
        
        # Normalize
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        return scores
    
    def extract_key_phrases(self, text: str, top_k: int = 5) -> List[Dict]:
        """
        Extract key phrases that influenced the decision using attention.
        Falls back to simple keyword extraction if attention isn't available.
        """
        if not self.transformers_available:
            return self._fallback_key_phrases(text, top_k)
        
        try:
            # Try to get attentions
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.device)
            
            with torch.no_grad():
                # Request attentions, but handle gracefully if not available
                outputs = self.model(**inputs, output_attentions=True)
            
            # Check if attentions are available
            if not hasattr(outputs, 'attentions') or outputs.attentions is None:
                print("⚠️ Model doesn't output attentions, using fallback")
                return self._fallback_key_phrases(text, top_k)
            
            # Get attention weights from the last layer
            # For BART, attentions are a tuple of layers, each with shape (batch, heads, seq_len, seq_len)
            last_layer_attention = outputs.attentions[-1]
            
            # Average across attention heads
            avg_attention = last_layer_attention.mean(dim=1)  # Shape: (batch, seq_len, seq_len)
            
            # Get attention to [CLS] token (first token) as importance measure
            cls_attention = avg_attention[0, 0, :]  # Attention from CLS to all tokens
            
            # Convert to numpy
            attention_scores = cls_attention.cpu().numpy()
            
            # Get tokens
            tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
            
            # Pair tokens with attention scores
            token_scores = list(zip(tokens, attention_scores))
            
            # Filter out special tokens and punctuation
            important_phrases = []
            current_phrase = []
            current_score = 0
            
            for token, score in token_scores:
                # Skip special tokens
                if token in ['<s>', '</s>', '<pad>', '[CLS]', '[SEP]', '[PAD]', '<unk>']:
                    if current_phrase:
                        important_phrases.append({
                            'phrase': ' '.join(current_phrase),
                            'score': float(current_score / len(current_phrase))
                        })
                        current_phrase = []
                        current_score = 0
                # Skip punctuation
                elif re.match(r'^[^\w]+$', token):
                    continue
                else:
                    # Clean token (remove special characters)
                    clean_token = token.replace('Ġ', '').replace('▁', '')
                    if clean_token and len(clean_token) > 1:  # Only keep meaningful words
                        current_phrase.append(clean_token)
                        current_score += score
            
            # Add last phrase
            if current_phrase:
                important_phrases.append({
                    'phrase': ' '.join(current_phrase),
                    'score': float(current_score / len(current_phrase))
                })
            
            # Sort by score and return top_k
            important_phrases.sort(key=lambda x: x['score'], reverse=True)
            
            # If no phrases extracted, use fallback
            if not important_phrases:
                return self._fallback_key_phrases(text, top_k)
                
            return important_phrases[:top_k]
            
        except Exception as e:
            print(f"⚠️ Error extracting key phrases: {e}")
            return self._fallback_key_phrases(text, top_k)
    
    def _fallback_key_phrases(self, text: str, top_k: int = 5) -> List[Dict]:
        """
        Simple keyword extraction fallback using TF-IDF style scoring.
        """
        # Simple stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could',
            'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'of',
            'with', 'from', 'by', 'about', 'as', 'into', 'like', 'through',
            'after', 'over', 'between', 'out', 'up', 'down', 'off', 'under'
        }
        
        # Split into words
        words = text.split()
        word_scores = {}
        total_words = len(words)
        
        # Simple importance based on length and position
        for i, word in enumerate(words):
            clean_word = word.lower().strip('.,!?;:""\'()[]{}')
            if len(clean_word) > 3 and clean_word not in stopwords:
                # Boost score for words that appear near the beginning
                position_boost = 1.0 + (0.5 * (1 - i/total_words))
                word_scores[clean_word] = word_scores.get(clean_word, 0) + position_boost
        
        # Normalize scores
        max_score = max(word_scores.values()) if word_scores else 1
        phrases = [{'phrase': word, 'score': score / max_score} 
                  for word, score in word_scores.items()]
        
        # Sort by score
        phrases.sort(key=lambda x: x['score'], reverse=True)
        return phrases[:top_k]
    
    def classify(self, text: str) -> Dict[str, Any]:
        """
        Main classification method that combines stance and key phrases.
        """
        # Get stance scores
        stance_scores = self.predict_stance(text)
        
        if not stance_scores:
            return {
                "stance": "neutral",
                "confidence": 0.5,
                "risk_score": 0.3,
                "key_phrases": [],
                "stance_scores": {}
            }
        
        # Determine primary stance
        stance_map = {
            "This text is spreading misinformation.": "spreading",
            "This text is fact-checking or debunking misinformation.": "debunking",
            "This text is neutral or educational.": "neutral",
            "This text is satirical or parody.": "satire",
            "This text is promoting a conspiracy theory.": "spreading",
            "This text is citing scientific evidence.": "credible",
            "This text is expressing a personal opinion.": "neutral",
            "This text is reporting news factually.": "credible"
        }
        
        # Find the hypothesis with highest score
        best_hypothesis = max(stance_scores, key=stance_scores.get)
        stance = stance_map.get(best_hypothesis, "neutral")
        confidence = stance_scores[best_hypothesis]
        
        # Extract key phrases
        key_phrases = self.extract_key_phrases(text)
        
        # Calculate risk score based on stance
        if stance == "spreading":
            risk_score = 0.7 + (confidence * 0.28)  # 0.7 to 0.98
        elif stance == "debunking":
            risk_score = 0.1 + (confidence * 0.2)   # 0.1 to 0.3
        elif stance == "credible":
            risk_score = 0.05 + (confidence * 0.15) # 0.05 to 0.2
        elif stance == "satire":
            risk_score = 0.1 + (confidence * 0.1)   # 0.1 to 0.2
        else:  # neutral
            risk_score = 0.3 + (confidence * 0.3)   # 0.3 to 0.6
        
        # Log classification for debugging
        print(f"🤖 BERT classified as: {stance} (confidence: {confidence:.2f}, risk: {risk_score:.2f})")
        
        return {
            "stance": stance,
            "confidence": confidence,
            "risk_score": min(risk_score, 0.98),
            "key_phrases": key_phrases,
            "stance_scores": stance_scores,
            "best_hypothesis": best_hypothesis
        }