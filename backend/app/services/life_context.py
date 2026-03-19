from __future__ import annotations

from app.models.agent import AgentPersona


DOMAIN_FLAVOR: dict[str, dict[str, str]] = {
    "finances": {
        "desperate": "You can't afford food. Every decision is about survival.",
        "struggling": "Money is a constant worry. You skip meals to save.",
        "tight but managing": "You make ends meet, but there's no safety net.",
        "stable": "Bills are paid. Not wealthy, but not worried.",
        "comfortable": "You have savings and breathing room.",
        "thriving": "Money is no concern. You think about legacy.",
    },
    "career": {
        "desperate": "You have no prospects. Doors keep closing.",
        "struggling": "Work is precarious. You fear being replaced.",
        "tight but managing": "You have a job, but no growth or recognition.",
        "stable": "Career is steady. You're competent and employed.",
        "comfortable": "You're respected in your field and advancing.",
        "thriving": "You're a leader in your domain. Opportunities find you.",
    },
    "health": {
        "desperate": "Your body is failing. Pain is constant.",
        "struggling": "Chronic issues drain your energy daily.",
        "tight but managing": "Health is okay but fragile. You push through.",
        "stable": "You're generally healthy with minor complaints.",
        "comfortable": "Strong and energetic. Body is an asset.",
        "thriving": "Peak condition. You feel unstoppable.",
    },
}

_LEVEL_THRESHOLDS: list[tuple[float, str]] = [
    (0.20, "desperate"),
    (0.35, "struggling"),
    (0.50, "tight but managing"),
    (0.65, "stable"),
    (0.80, "comfortable"),
    (1.01, "thriving"),
]

ECHO_CATEGORIES: dict[str, list[str]] = {
    "authority": ["rule", "law", "leader", "order"],
    "scarcity": ["lose", "crisis", "shortage"],
    "trust": ["trust", "promise", "betray", "lie"],
    "belonging": ["group", "faction", "belong", "exclude"],
}


def compute_domain_level(domain: str, value: float) -> str:
    level = "stable"
    for threshold, label in _LEVEL_THRESHOLDS:
        if value < threshold:
            level = label
            break

    flavor = DOMAIN_FLAVOR.get(domain, {}).get(level, "")
    if flavor:
        return f"{level} — {flavor}"
    return level


def compute_need_priority(agent: AgentPersona, current_day: int) -> str:
    ls = agent.life_state
    if ls is None:
        return ""

    for p in ls.pressures:
        if (
            p.deadline_day is not None
            and (p.deadline_day - current_day) <= 2
            and p.severity > 0.6
        ):
            return f"SURVIVAL MODE: {p.description} — you must act on this NOW"

    if ls.finances < 0.2 or ls.health < 0.2:
        return "Your basic needs are threatened"

    high_dep_names = [
        fm.name for fm in ls.family if fm.dependency > 0.5
    ]
    if high_dep_names and ls.finances < 0.4:
        return f"You have people depending on you ({', '.join(high_dep_names)})"

    if ls.career < 0.3:
        return "Your career is stagnating"

    if ls.finances > 0.7 and ls.career > 0.7 and ls.health > 0.7:
        return "Life is good — think about legacy and meaning"

    return "Life is manageable but not easy"


def compute_action_bias(agent: AgentPersona, current_day: int) -> dict[str, str]:
    ls = agent.life_state
    if ls is None:
        return {}

    biases: dict[str, str] = {}

    if ls.finances < 0.25:
        biases["TRADE"] = "(you NEED resources)"
        biases["BUILD"] = "(can't afford to spend)"
        total_dep = sum(fm.dependency for fm in ls.family)
        if total_dep > 0.5:
            biases["DEFECT"] = "(but your family would pay the price)"
        else:
            biases["DEFECT"] = "(desperate times…)"

    if ls.health < 0.25:
        biases["BUILD"] = "(no physical energy)"
        biases["PROTEST"] = "(too exhausted)"
        biases["OBSERVE"] = "(conserving energy)"

    total_dep = sum(fm.dependency for fm in ls.family)
    if total_dep > 1.0:
        biases.setdefault("DEFECT", "")
        biases["DEFECT"] = "(your family needs you safe)" + (
            " " + biases["DEFECT"] if biases["DEFECT"] else ""
        )
        biases.setdefault("PROTEST", "")
        biases["PROTEST"] = "(think of the people counting on you)" + (
            " " + biases["PROTEST"] if biases["PROTEST"] else ""
        )

    if ls.career < 0.25:
        biases["COMPLY"] = "(need to be seen as reliable)"

    for p in ls.pressures:
        if (
            p.deadline_day is not None
            and (p.deadline_day - current_day) <= 2
            and p.severity > 0.5
        ):
            biases["DO_NOTHING"] = f"(URGENT: {p.description} deadline imminent)"
            biases.setdefault("OBSERVE", "")
            existing = biases["OBSERVE"]
            warning = f"(deadline looming: {p.description})"
            biases["OBSERVE"] = (
                f"{existing} {warning}".strip() if existing else warning
            )
            break

    if ls.finances > 0.75 and ls.career > 0.7:
        biases.setdefault("PROPOSE_RULE", "(you have the standing to lead)")
        biases.setdefault("BUILD", "(you have resources to invest)")
        biases.setdefault("FORM_GROUP", "(people look up to you)")

    return biases


def find_relevant_echoes(agent: AgentPersona, context: str) -> list[str]:
    ls = agent.life_state
    if ls is None or not ls.formative_events:
        return []

    ctx_lower = context.lower()
    matched_categories: set[str] = set()
    for category, keywords in ECHO_CATEGORIES.items():
        for kw in keywords:
            if kw in ctx_lower:
                matched_categories.add(category)
                break

    if not matched_categories:
        return []

    echoes: list[str] = []
    for event in ls.formative_events:
        event_text = f"{event.description} {event.lasting_effect}".lower()
        for category in matched_categories:
            for kw in ECHO_CATEGORIES[category]:
                if kw in event_text:
                    echoes.append(
                        f"Echo from your past: {event.description} → {event.lasting_effect}"
                    )
                    break
            else:
                continue
            break

    return echoes[:2]


def build_life_prompt_block(
    agent: AgentPersona, current_day: int, context: str
) -> str:
    ls = agent.life_state
    if ls is None:
        return ""

    lines: list[str] = []
    lines.append("=== YOUR LIFE RIGHT NOW ===")

    for domain in ("finances", "career", "health"):
        value = getattr(ls, domain)
        lines.append(f"  {domain.capitalize()}: {compute_domain_level(domain, value)}")

    if ls.family:
        family_parts = [
            f"{fm.name} ({fm.relation}, {fm.status})" for fm in ls.family
        ]
        lines.append(f"  Family: {', '.join(family_parts)}")

    if ls.pressures:
        lines.append("  Active pressures:")
        for p in ls.pressures:
            deadline_str = f" [deadline: day {p.deadline_day}]" if p.deadline_day is not None else ""
            lines.append(f"    - {p.description} (severity {p.severity:.1f}){deadline_str}")

    priority = compute_need_priority(agent, current_day)
    if priority:
        lines.append(f"  >>> {priority}")

    biases = compute_action_bias(agent, current_day)
    if biases:
        bias_parts = [f"{k}: {v}" for k, v in biases.items()]
        lines.append(f"  Action notes: {'; '.join(bias_parts)}")

    lines.append("")
    lines.append("=== YOUR HISTORY ===")
    lines.append(f"  Childhood: {ls.childhood_summary}")

    if ls.formative_events:
        for fe in ls.formative_events:
            lines.append(f"  - Age {fe.age_at_event}: {fe.description} → {fe.lasting_effect}")

    echoes = find_relevant_echoes(agent, context)
    if echoes:
        lines.append("")
        for echo in echoes:
            lines.append(f"  ** {echo} **")

    return "\n".join(lines)
