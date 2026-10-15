import re
from typing import Any, Dict, List

WORD_RE = re.compile(r"[a-zA-Z']+")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
CASUAL_MARKERS = {"lol", "gonna", "wanna", "hey", "yo", "kinda", "sorta", "ur", "u"}

"""Shared, dependency-free deterministic text heuristics used by both the Intelligence
Layer's EvaluationEngine (agent output QA) and ContentQualityEngine (content-specific
scoring), so the two never drift into different definitions of "readable" or
"grounded". None of this calls an LLM - see docs/PROJECT_RULES.md Rule 1/the audit's
"deterministic calculations must stay deterministic" requirement."""


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in WORD_RE.findall(text or "")]


def count_syllables(word: str) -> int:
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    previous_was_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not previous_was_vowel:
            count += 1
        previous_was_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def extract_source_text(source_context: Dict[str, Any]) -> str:
    """Pulls every string value out of a loosely-shaped knowledge/source context dict
    so groundedness/hallucination checks have something concrete to compare against."""
    parts: List[str] = []

    def _walk(value):
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for v in value:
                _walk(v)

    _walk(source_context)
    return "\n".join(parts)


def groundedness_score(generated_content: str, source_text: str) -> int:
    """% of the generated content's distinct words that also appear in the source text."""
    generated_words = set(tokenize(generated_content))
    if not generated_words:
        return 0
    source_words = set(tokenize(source_text))
    if not source_words:
        return 0
    overlap = generated_words & source_words
    return int(round(100 * len(overlap) / len(generated_words)))


def completeness_score(generated_content: str, min_word_count: int = 150) -> int:
    word_count = len(tokenize(generated_content))
    return int(round(min(100, 100 * word_count / min_word_count)))


def citation_coverage_score(source_context: Dict[str, Any]) -> int:
    for value in source_context.values() if isinstance(source_context, dict) else []:
        if isinstance(value, dict):
            sources = value.get("sources") or value.get("citations")
            if sources:
                return 100
    return 0


def readability_score(generated_content: str) -> int:
    """Flesch Reading Ease, clamped to 0-100."""
    words = tokenize(generated_content)
    if not words:
        return 0
    sentences = [s for s in SENTENCE_SPLIT_RE.split(generated_content) if s.strip()]
    sentence_count = max(1, len(sentences))
    syllable_count = sum(count_syllables(w) for w in words)
    score = 206.835 - 1.015 * (len(words) / sentence_count) - 84.6 * (syllable_count / len(words))
    return int(round(max(0, min(100, score))))


def professional_tone_score(generated_content: str) -> int:
    if not generated_content.strip():
        return 0
    score = 100
    score -= 10 * generated_content.count("!")
    words = generated_content.split()
    shouting_words = [w for w in words if len(w) > 2 and w.isupper()]
    score -= 5 * len(shouting_words)
    lowered_words = set(tokenize(generated_content))
    score -= 15 * len(lowered_words & CASUAL_MARKERS)
    return int(round(max(0, min(100, score))))


def hallucination_risk_score(generated_content: str, source_text: str) -> int:
    """Numbers/percentages in the generated content absent from the source text -
    lower is better, 0 = every number is traceable to source."""
    generated_numbers = set(NUMBER_RE.findall(generated_content or ""))
    if not generated_numbers:
        return 0
    source_numbers = set(NUMBER_RE.findall(source_text or ""))
    unmatched = generated_numbers - source_numbers
    if not unmatched:
        return 0
    return int(round(min(100, 100 * len(unmatched) / len(generated_numbers))))


def originality_score(generated_content: str, source_text: str, ngram_size: int = 8) -> int:
    """100 minus the fraction of the generated content's word-ngrams that are copied
    verbatim from the source - flags near-copy-paste rather than genuinely written text."""
    gen_words = tokenize(generated_content)
    if len(gen_words) < ngram_size:
        return 100
    source_words = tokenize(source_text)
    if len(source_words) < ngram_size:
        return 100

    source_ngrams = {tuple(source_words[i:i + ngram_size]) for i in range(len(source_words) - ngram_size + 1)}
    gen_ngrams = [tuple(gen_words[i:i + ngram_size]) for i in range(len(gen_words) - ngram_size + 1)]
    if not gen_ngrams:
        return 100
    copied = sum(1 for g in gen_ngrams if g in source_ngrams)
    return int(round(100 * (1 - copied / len(gen_ngrams))))


def grammar_score(generated_content: str) -> int:
    """Crude, dependency-free grammar sanity checks: sentence capitalization, terminal
    punctuation, no immediate word repetition, no doubled spaces. Not a real grammar
    checker - a deterministic floor, not a ceiling, on obviously malformed output."""
    text = (generated_content or "").strip()
    if not text:
        return 0

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return 0

    checks_passed = 0
    checks_total = 0

    for sentence in sentences:
        checks_total += 1
        if sentence[:1].isupper():
            checks_passed += 1

    checks_total += 1
    if "  " not in text:
        checks_passed += 1

    words = tokenize(text)
    checks_total += 1
    repeated_pairs = any(words[i] == words[i + 1] for i in range(len(words) - 1))
    if not repeated_pairs:
        checks_passed += 1

    return int(round(100 * checks_passed / checks_total))


def brand_consistency_score(text: str, brand_rules: Dict[str, Any]) -> int:
    """Re-runs the same forbidden-term/required-keyword checks BrandVoiceValidator
    enforces, expressed as a 0-100 score instead of a pass/fail, for use in the overall
    ContentScore. Returns 100 when no brand rules are configured (nothing to violate)."""
    forbidden_terms = (brand_rules or {}).get("forbidden_terms", [])
    required_keywords = (brand_rules or {}).get("required_keywords", [])
    checks_total = len(forbidden_terms) + len(required_keywords)
    if checks_total == 0:
        return 100

    lowered = (text or "").lower()
    checks_passed = sum(1 for term in forbidden_terms if term.lower() not in lowered)
    checks_passed += sum(1 for kw in required_keywords if kw.lower() in lowered)
    return int(round(100 * checks_passed / checks_total))
