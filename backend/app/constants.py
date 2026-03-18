from __future__ import annotations

TIMES_OF_DAY = ["morning", "afternoon", "evening"]

VALID_EMOTIONAL_STATES = [
    "calm", "content", "curious", "satisfied", "hopeful",
    "restless", "frustrated", "dissatisfied", "uneasy", "anxious",
    "angry", "fearful", "hostile", "desperate",
    "conflicted", "torn", "confused",
]

def normalize_emotional_state(raw: str) -> str:
    if not raw:
        return "calm"
    lower = raw.lower().strip()
    for state in VALID_EMOTIONAL_STATES:
        if state in lower:
            return state
    if any(w in lower for w in ("happy", "joy", "pleased", "glad", "happiness")):
        return "content"
    if any(w in lower for w in ("worry", "nervous", "uncertain", "anxiety", "anxiet")):
        return "anxious"
    if any(w in lower for w in ("sad", "sorrow", "grief", "mourn")):
        return "dissatisfied"
    if any(w in lower for w in ("rage", "fury", "furious", "outraged")):
        return "angry"
    if any(w in lower for w in ("scared", "terrified", "afraid")):
        return "fearful"
    if any(w in lower for w in ("bored", "tired", "weary")):
        return "restless"
    if any(w in lower for w in ("excited", "eager", "enthusiastic")):
        return "hopeful"
    if any(w in lower for w in ("suspicious", "wary", "distrustful")):
        return "uneasy"
    return "calm"
