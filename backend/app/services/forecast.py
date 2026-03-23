from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    from darts import TimeSeries
    from darts.models import ExponentialSmoothing, Theta
    from darts.utils.statistics import (
        check_seasonality,
        extract_trend_and_seasonality,
        granger_causality_tests,
        stationarity_tests,
    )
    from darts.ad.detectors import QuantileDetector
    from darts.ad.scorers import NormScorer

    DARTS_AVAILABLE = True
except ImportError:
    DARTS_AVAILABLE = False
    logger.warning("darts not installed — ForecastService will be disabled")


METRIC_KEYS_SOCIAL = ["stability", "prosperity", "trust", "freedom", "conflict"]
METRIC_KEYS_MARKET = [
    "brand_sentiment",
    "purchase_intent",
    "word_of_mouth",
    "churn_risk",
    "adoption_rate",
]
ALL_METRIC_KEYS = METRIC_KEYS_SOCIAL + METRIC_KEYS_MARKET

ACTION_ENCODING = {
    "DO_NOTHING": 0,
    "OBSERVE": 1,
    "COMPLY": 2,
    "SPEAK_PUBLIC": 3,
    "SPEAK_PRIVATE": 3,
    "TRADE": 4,
    "COMPARE": 5,
    "RESEARCH": 5,
    "INVESTIGATE": 5,
    "RECOMMEND": 6,
    "PURCHASE": 6,
    "FORM_GROUP": 7,
    "PROPOSE_RULE": 7,
    "VOTE": 7,
    "BUILD": 7,
    "PROTEST": 8,
    "ABANDON": 9,
    "DEFECT": 10,
}

REFIT_INTERVAL = 5
MIN_HISTORY_FOR_MODEL = 10
MIN_HISTORY_FOR_CAUSALITY = 30
CLAMP_SIGMA_MULTIPLIER = 2.0
CLAMP_DAMPING = 0.5
COHERENCE_THRESHOLD = 0.5


@dataclass
class AgentCoherenceScore:
    agent_id: int
    score: float
    contradictions: list[str] = field(default_factory=list)
    correction_hint: str = ""


@dataclass
class CausalLink:
    cause: str
    effect: str
    lag: int
    p_value: float
    strength: str


@dataclass
class CounterfactualResult:
    event_round: int
    event_description: str
    metric_impacts: dict[str, float] = field(default_factory=dict)
    projected_without_event: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class _SimState:
    fitted_models: dict[str, Any] = field(default_factory=dict)
    metric_series: dict[str, list[float]] = field(default_factory=dict)
    metric_std: dict[str, float] = field(default_factory=dict)
    metric_trend: dict[str, float] = field(default_factory=dict)
    agent_action_series: dict[int, list[int]] = field(default_factory=dict)
    coherence_scores: dict[int, AgentCoherenceScore] = field(default_factory=dict)
    causal_links: list[CausalLink] = field(default_factory=list)
    counterfactuals: list[CounterfactualResult] = field(default_factory=list)
    event_snapshots: dict[int, dict[str, Any]] = field(default_factory=dict)
    last_fit_round: int = 0
    rounds_seen: int = 0


class ForecastService:
    """Statistical intelligence layer for MiroSociety simulations.

    Provides trend grounding for agent prompts, metric clamping for the
    resolver, stationarity-based disruption detection for the tension engine,
    agent coherence scoring, Granger-causal discovery between metrics,
    and counterfactual analysis for tension events.

    All methods gracefully return fallbacks when Darts is unavailable or
    when insufficient data has accumulated.
    """

    def __init__(self):
        self._sims: dict[str, _SimState] = {}

    @property
    def available(self) -> bool:
        return DARTS_AVAILABLE

    def init_simulation(self, sim_id: str):
        self._sims[sim_id] = _SimState()

    def cleanup(self, sim_id: str):
        self._sims.pop(sim_id, None)

    def _state(self, sim_id: str) -> _SimState:
        if sim_id not in self._sims:
            self._sims[sim_id] = _SimState()
        return self._sims[sim_id]

    # ------------------------------------------------------------------
    # Core update — called every round from engine.py
    # ------------------------------------------------------------------

    def update(
        self,
        sim_id: str,
        metrics_history: list[dict],
        agent_actions: dict[int, str] | None = None,
    ):
        if not DARTS_AVAILABLE:
            return

        st = self._state(sim_id)
        st.rounds_seen = len(metrics_history)

        for key in ALL_METRIC_KEYS:
            st.metric_series[key] = [m.get(key, 0.5) for m in metrics_history]

        if agent_actions:
            for agent_id, action_str in agent_actions.items():
                encoded = ACTION_ENCODING.get(action_str, 0)
                st.agent_action_series.setdefault(agent_id, []).append(encoded)

        if (
            st.rounds_seen >= MIN_HISTORY_FOR_MODEL
            and st.rounds_seen - st.last_fit_round >= REFIT_INTERVAL
        ):
            self._refit(st)
            st.last_fit_round = st.rounds_seen

    def _refit(self, st: _SimState):
        for key in ALL_METRIC_KEYS:
            values = st.metric_series.get(key, [])
            if len(values) < MIN_HISTORY_FOR_MODEL:
                continue
            try:
                arr = np.array(values, dtype=np.float64)
                ts = TimeSeries.from_values(arr)
                model = ExponentialSmoothing()
                model.fit(ts)
                st.fitted_models[key] = model

                if len(values) >= 5:
                    recent = values[-5:]
                    st.metric_std[key] = float(np.std(recent)) if len(recent) > 1 else 0.05

                if len(values) >= 3:
                    diffs = [values[i] - values[i - 1] for i in range(-min(5, len(values) - 1), 0)]
                    st.metric_trend[key] = float(np.mean(diffs)) if diffs else 0.0
            except Exception as e:
                logger.debug("Failed to fit model for %s: %s", key, e)

    # ------------------------------------------------------------------
    # trend_context — statistical summary for agent prompts
    # ------------------------------------------------------------------

    def trend_context(self, sim_id: str, metric_keys: list[str] | None = None) -> str:
        if not DARTS_AVAILABLE:
            return ""

        st = self._state(sim_id)
        if st.rounds_seen < MIN_HISTORY_FOR_MODEL:
            return ""

        keys = metric_keys or [k for k in ALL_METRIC_KEYS if st.metric_series.get(k)]
        lines = []

        for key in keys:
            values = st.metric_series.get(key, [])
            if not values:
                continue

            current = values[-1]
            trend = st.metric_trend.get(key, 0.0)
            std = st.metric_std.get(key, 0.05)
            label = key.replace("_", " ").title()

            if abs(trend) < std * 0.3:
                direction = "STABLE"
                detail = f"(+/-{std:.2f} over last 5 rounds)"
            elif trend > 0:
                direction = "trending UP"
                projected = min(1.0, current + trend * 10)
                detail = f"(+{trend:.3f}/round, projected {projected:.2f} in 10 rounds)"
            else:
                direction = "trending DOWN"
                projected = max(0.0, current + trend * 10)
                detail = f"({trend:.3f}/round, projected {projected:.2f} in 10 rounds)"

            model = st.fitted_models.get(key)
            acceleration = ""
            if model and len(values) >= 10:
                try:
                    recent_trend = np.mean(
                        [values[i] - values[i - 1] for i in range(-3, 0)]
                    )
                    older_trend = np.mean(
                        [values[i] - values[i - 1] for i in range(-6, -3)]
                    )
                    if abs(recent_trend) > abs(older_trend) * 1.5 and abs(trend) > std * 0.3:
                        acceleration = ", ACCELERATING"
                    elif abs(recent_trend) < abs(older_trend) * 0.5 and abs(trend) > std * 0.3:
                        acceleration = ", decelerating"
                except (IndexError, ZeroDivisionError):
                    pass

            lines.append(f"- {label}: {current:.2f}, {direction} {detail}{acceleration}")

        if not lines:
            return ""

        return (
            "STATISTICAL REALITY CHECK (actual measured data, not opinions):\n"
            + "\n".join(lines)
            + "\nNOTE: These are statistical facts from simulation data. "
            "Your personal opinion may differ, but these are the real numbers."
        )

    # ------------------------------------------------------------------
    # clamp_metrics — constrain resolver output via mean-reversion
    # ------------------------------------------------------------------

    def clamp_metrics(
        self,
        sim_id: str,
        proposed: dict[str, float],
        current: dict[str, float],
    ) -> dict[str, float]:
        if not DARTS_AVAILABLE:
            return proposed

        st = self._state(sim_id)
        if st.rounds_seen < MIN_HISTORY_FOR_MODEL:
            return proposed

        clamped = dict(proposed)

        for key in ALL_METRIC_KEYS:
            if key not in proposed or key not in current:
                continue

            model = st.fitted_models.get(key)
            std = st.metric_std.get(key, 0.05)
            trend = st.metric_trend.get(key, 0.0)

            if model is None:
                continue

            expected = current[key] + trend
            expected = max(0.0, min(1.0, expected))

            proposed_val = proposed[key]
            deviation = proposed_val - expected

            threshold = CLAMP_SIGMA_MULTIPLIER * max(std, 0.02)
            if abs(deviation) > threshold:
                damped = expected + math.copysign(threshold, deviation) + (
                    deviation - math.copysign(threshold, deviation)
                ) * CLAMP_DAMPING
                clamped[key] = max(0.0, min(1.0, damped))

        return clamped

    # ------------------------------------------------------------------
    # check_anomalies — detect unrealistic metric movements
    # ------------------------------------------------------------------

    def check_anomalies(self, sim_id: str) -> list[dict]:
        if not DARTS_AVAILABLE:
            return []

        st = self._state(sim_id)
        if st.rounds_seen < MIN_HISTORY_FOR_MODEL + 3:
            return []

        anomalies = []

        for key in ALL_METRIC_KEYS:
            values = st.metric_series.get(key, [])
            model = st.fitted_models.get(key)
            std = st.metric_std.get(key, 0.05)

            if not model or len(values) < MIN_HISTORY_FOR_MODEL:
                continue

            try:
                latest = values[-1]
                prev = values[-2] if len(values) >= 2 else latest
                trend = st.metric_trend.get(key, 0.0)
                expected = prev + trend
                deviation = abs(latest - expected)

                threshold = CLAMP_SIGMA_MULTIPLIER * max(std, 0.02)
                if deviation > threshold:
                    severity = min(1.0, deviation / max(threshold, 0.01))
                    direction = "spike" if latest > expected else "drop"
                    anomalies.append({
                        "metric": key,
                        "label": key.replace("_", " ").title(),
                        "round": st.rounds_seen,
                        "expected": round(expected, 4),
                        "actual": round(latest, 4),
                        "deviation": round(deviation, 4),
                        "severity": round(severity, 2),
                        "direction": direction,
                        "description": (
                            f"{key.replace('_', ' ').title()} showed an unexpected {direction} "
                            f"({latest:.2f} vs expected {expected:.2f}, "
                            f"{severity:.0%} beyond normal range)"
                        ),
                    })
            except Exception as e:
                logger.debug("Anomaly check failed for %s: %s", key, e)

        return anomalies

    # ------------------------------------------------------------------
    # should_disrupt — stationarity-based disruption trigger
    # ------------------------------------------------------------------

    def should_disrupt(self, sim_id: str) -> bool:
        if not DARTS_AVAILABLE:
            return False

        st = self._state(sim_id)
        if st.rounds_seen < MIN_HISTORY_FOR_MODEL:
            return False

        stationary_count = 0
        tested_count = 0

        for key in ALL_METRIC_KEYS:
            values = st.metric_series.get(key, [])
            if len(values) < MIN_HISTORY_FOR_MODEL:
                continue
            tested_count += 1
            try:
                arr = np.array(values[-15:], dtype=np.float64)
                ts = TimeSeries.from_values(arr)
                is_stationary = stationarity_tests(ts)
                if is_stationary:
                    stationary_count += 1
            except Exception:
                pass

        if tested_count == 0:
            return False

        return stationary_count / tested_count >= 0.8

    # ------------------------------------------------------------------
    # score_agent_coherence — detect agents acting out of character
    # ------------------------------------------------------------------

    _BRAND_NEGATIVE_KW = frozenset({
        "frustrated", "angry", "disappointed", "betrayed", "ridiculous",
        "unacceptable", "greed", "cancel", "leaving", "done with",
        "can't believe", "outrageous", "unfair", "overpriced", "rip-off",
        "too expensive", "not worth", "cash grab", "price hike",
    })
    _BRAND_POSITIVE_KW = frozenset({
        "love", "great", "worth", "enjoy", "amazing", "loyal", "staying",
        "recommend", "value", "appreciate", "satisfied", "good deal", "fair",
        "quality", "defend", "support",
    })

    def score_agent_coherence(
        self,
        sim_id: str,
        agents: list[Any],
    ) -> dict[int, AgentCoherenceScore]:
        st = self._state(sim_id)
        results: dict[int, AgentCoherenceScore] = {}

        for agent in agents:
            aid = agent.id
            action_history = st.agent_action_series.get(aid, [])

            if len(action_history) < 3:
                results[aid] = AgentCoherenceScore(agent_id=aid, score=1.0)
                continue

            contradictions: list[str] = []
            score = 1.0
            p = agent.personality

            recent = action_history[-5:] if len(action_history) >= 5 else action_history[:]

            if p.brand_loyalty >= 0.7:
                has_abandon = any(v >= ACTION_ENCODING.get("ABANDON", 9) for v in recent)
                has_prior_escalation = any(
                    ACTION_ENCODING.get("PROTEST", 8) <= v <= ACTION_ENCODING.get("ABANDON", 9)
                    for v in action_history[:-3]
                ) if len(action_history) > 3 else False
                if has_abandon and not has_prior_escalation:
                    contradictions.append(
                        f"brand_loyalty={p.brand_loyalty:.1f} but ABANDONED "
                        f"without prior escalation (no PROTEST or COMPARE first)"
                    )
                    score -= 0.4

                speech_mems = [m.lower() for m in agent.working_memory if "said" in m.lower()]
                recent_speech = speech_mems[-3:] if len(speech_mems) >= 3 else speech_mems
                if len(recent_speech) >= 2:
                    neg_count = sum(
                        1 for mem in recent_speech
                        if any(kw in mem for kw in self._BRAND_NEGATIVE_KW)
                    )
                    pos_count = sum(
                        1 for mem in recent_speech
                        if any(kw in mem for kw in self._BRAND_POSITIVE_KW)
                    )
                    if neg_count >= 2 and pos_count == 0:
                        contradictions.append(
                            f"brand_loyalty={p.brand_loyalty:.1f} but ALL recent speech "
                            f"is negative about the brand with zero defense. "
                            f"A loyal person would find something positive to say."
                        )
                        score -= 0.3

            if p.conformity >= 0.7:
                defect_count = sum(1 for v in recent if v >= ACTION_ENCODING.get("DEFECT", 10))
                if defect_count >= 2:
                    contradictions.append(
                        f"conformity={p.conformity:.1f} but DEFECTed {defect_count} "
                        f"times in last 5 rounds"
                    )
                    score -= 0.3

            if p.price_sensitivity <= 0.3:
                abandon_for_price = sum(
                    1 for v in recent if v >= ACTION_ENCODING.get("ABANDON", 9)
                )
                if abandon_for_price >= 1:
                    contradictions.append(
                        f"price_sensitivity={p.price_sensitivity:.1f} but "
                        f"showing exit behavior despite low price sensitivity"
                    )
                    score -= 0.25

            if len(action_history) >= 6:
                oscillations = 0
                for i in range(-5, -1):
                    diff = abs(action_history[i] - action_history[i + 1])
                    if diff >= 5:
                        oscillations += 1
                if oscillations >= 3:
                    contradictions.append(
                        f"Oscillating wildly between cooperative and adversarial "
                        f"actions ({oscillations} swings in 5 rounds)"
                    )
                    score -= 0.3

            score = max(0.0, min(1.0, score))

            hint = ""
            if score < COHERENCE_THRESHOLD and contradictions:
                hint = (
                    "BEHAVIORAL CHECK: Your recent actions are inconsistent with who you are. "
                    + " ".join(contradictions)
                    + " Consider whether your recent choices truly reflect your personality "
                    "and values, or if you were swept up in the moment."
                )

            results[aid] = AgentCoherenceScore(
                agent_id=aid,
                score=score,
                contradictions=contradictions,
                correction_hint=hint,
            )

        st.coherence_scores = results
        return results

    def get_coherence_hint(self, sim_id: str, agent_id: int) -> str:
        st = self._state(sim_id)
        cs = st.coherence_scores.get(agent_id)
        if cs and cs.score < COHERENCE_THRESHOLD:
            return cs.correction_hint
        return ""

    # ------------------------------------------------------------------
    # discover_causality — Granger causality between metric pairs
    # ------------------------------------------------------------------

    def discover_causality(self, sim_id: str) -> list[CausalLink]:
        if not DARTS_AVAILABLE:
            return []

        st = self._state(sim_id)
        if st.rounds_seen < MIN_HISTORY_FOR_CAUSALITY:
            return []

        active_keys = [
            k for k in ALL_METRIC_KEYS
            if len(st.metric_series.get(k, [])) >= MIN_HISTORY_FOR_CAUSALITY
        ]

        links: list[CausalLink] = []

        for cause_key in active_keys:
            for effect_key in active_keys:
                if cause_key == effect_key:
                    continue
                try:
                    cause_arr = np.array(
                        st.metric_series[cause_key][-MIN_HISTORY_FOR_CAUSALITY:],
                        dtype=np.float64,
                    )
                    effect_arr = np.array(
                        st.metric_series[effect_key][-MIN_HISTORY_FOR_CAUSALITY:],
                        dtype=np.float64,
                    )

                    if np.std(cause_arr) < 0.01 or np.std(effect_arr) < 0.01:
                        continue

                    ts_cause = TimeSeries.from_values(cause_arr)
                    ts_effect = TimeSeries.from_values(effect_arr)

                    max_lag = min(5, len(cause_arr) // 5)
                    if max_lag < 1:
                        continue

                    result = granger_causality_tests(ts_cause, ts_effect, maxlag=max_lag)

                    best_lag = None
                    best_p = 1.0
                    for lag_val, (test_dict, *_) in result.items():
                        p_val = test_dict["ssr_ftest"][1]
                        if p_val < best_p:
                            best_p = p_val
                            best_lag = lag_val

                    if best_p < 0.05 and best_lag is not None:
                        if best_p < 0.01:
                            strength = "strong"
                        elif best_p < 0.03:
                            strength = "moderate"
                        else:
                            strength = "weak"

                        links.append(CausalLink(
                            cause=cause_key,
                            effect=effect_key,
                            lag=best_lag,
                            p_value=round(best_p, 4),
                            strength=strength,
                        ))
                except Exception as e:
                    logger.debug(
                        "Granger test failed for %s -> %s: %s",
                        cause_key, effect_key, e,
                    )

        links.sort(key=lambda l: l.p_value)
        st.causal_links = links[:20]
        return st.causal_links

    # ------------------------------------------------------------------
    # Counterfactual analysis
    # ------------------------------------------------------------------

    def snapshot_for_counterfactual(
        self, sim_id: str, event_round: int, event_description: str
    ):
        if not DARTS_AVAILABLE:
            return

        st = self._state(sim_id)
        snapshot: dict[str, Any] = {"description": event_description, "models": {}}

        for key in ALL_METRIC_KEYS:
            values = st.metric_series.get(key, [])
            if len(values) < MIN_HISTORY_FOR_MODEL:
                continue
            try:
                arr = np.array(values, dtype=np.float64)
                ts = TimeSeries.from_values(arr)
                model = Theta()
                model.fit(ts)
                snapshot["models"][key] = model
            except Exception as e:
                logger.debug("Counterfactual snapshot failed for %s: %s", key, e)

        st.event_snapshots[event_round] = snapshot

    def compute_counterfactuals(self, sim_id: str) -> list[CounterfactualResult]:
        if not DARTS_AVAILABLE:
            return []

        st = self._state(sim_id)
        results: list[CounterfactualResult] = []

        for event_round, snapshot in st.event_snapshots.items():
            horizon = st.rounds_seen - event_round
            if horizon < 3:
                continue

            impacts: dict[str, float] = {}
            projected: dict[str, list[float]] = {}

            for key, model in snapshot.get("models", {}).items():
                try:
                    forecast = model.predict(horizon)
                    forecast_values = forecast.values().flatten().tolist()
                    projected[key] = [round(v, 4) for v in forecast_values]

                    actual_values = st.metric_series.get(key, [])
                    if len(actual_values) >= st.rounds_seen:
                        actual_end = actual_values[-1]
                        projected_end = forecast_values[-1] if forecast_values else actual_end
                        impacts[key] = round(actual_end - projected_end, 4)
                except Exception as e:
                    logger.debug("Counterfactual projection failed for %s: %s", key, e)

            results.append(CounterfactualResult(
                event_round=event_round,
                event_description=snapshot.get("description", "Unknown event"),
                metric_impacts=impacts,
                projected_without_event=projected,
            ))

        st.counterfactuals = results
        return results

    # ------------------------------------------------------------------
    # Full post-simulation analysis
    # ------------------------------------------------------------------

    def analyze(self, metrics_history: list[dict], horizon: int = 30) -> dict:
        if not DARTS_AVAILABLE or len(metrics_history) < MIN_HISTORY_FOR_MODEL:
            return {}

        result: dict[str, Any] = {
            "projections": [],
            "trend_analysis": {},
            "seasonality": {},
            "anomalies": [],
        }

        for key in ALL_METRIC_KEYS:
            values = [m.get(key, 0.5) for m in metrics_history]
            if len(values) < MIN_HISTORY_FOR_MODEL:
                continue

            arr = np.array(values, dtype=np.float64)
            ts = TimeSeries.from_values(arr)

            try:
                model = ExponentialSmoothing()
                model.fit(ts)
                pred_horizon = max(1, min(horizon, max(1, len(values) // 3)))
                forecast = model.predict(pred_horizon)
                forecast_vals = forecast.values().flatten().tolist()

                result["projections"].append({
                    "metric": key,
                    "label": key.replace("_", " ").title(),
                    "current": round(values[-1], 4),
                    "projected": [round(v, 4) for v in forecast_vals],
                    "projected_end": round(forecast_vals[-1], 4) if forecast_vals else None,
                    "horizon_rounds": pred_horizon,
                })
            except Exception as e:
                logger.debug("Projection failed for %s: %s", key, e)

            try:
                trend, seasonal = extract_trend_and_seasonality(ts, freq=3)
                trend_vals = trend.values().flatten().tolist() if trend is not None else []
                if len(trend_vals) >= 2:
                    trend_direction = trend_vals[-1] - trend_vals[0]
                    recent_acceleration = 0.0
                    if len(trend_vals) >= 6:
                        early = trend_vals[len(trend_vals) // 2] - trend_vals[0]
                        late = trend_vals[-1] - trend_vals[len(trend_vals) // 2]
                        if abs(early) > 0.001:
                            recent_acceleration = (late - early) / abs(early)

                    result["trend_analysis"][key] = {
                        "direction": round(trend_direction, 4),
                        "accelerating": recent_acceleration > 0.3,
                        "decelerating": recent_acceleration < -0.3,
                    }
            except Exception as e:
                logger.debug("Trend extraction failed for %s: %s", key, e)

            try:
                is_seasonal, period = check_seasonality(ts, m=3, max_lag=12)
                if is_seasonal:
                    result["seasonality"][key] = {
                        "detected": True,
                        "period": period,
                        "description": (
                            f"{key.replace('_', ' ').title()} shows a cyclical pattern "
                            f"with period {period} (likely aligned with day/night cycle)"
                        ),
                    }
            except Exception as e:
                logger.debug("Seasonality check failed for %s: %s", key, e)

        return result
