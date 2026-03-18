export const SOCIAL_METRICS = [
  { key: 'stability', label: 'Stability', color: 'bg-emerald-500', goodHigh: true },
  { key: 'prosperity', label: 'Prosperity', color: 'bg-blue-400', goodHigh: true },
  { key: 'trust', label: 'Trust', color: 'bg-violet-400', goodHigh: true },
  { key: 'freedom', label: 'Freedom', color: 'bg-amber-400', goodHigh: true },
  { key: 'conflict', label: 'Conflict', color: 'bg-red-500', goodHigh: false },
]

export const MARKET_METRICS = [
  { key: 'brand_sentiment', label: 'Sentiment', color: 'bg-emerald-400', goodHigh: true },
  { key: 'purchase_intent', label: 'Intent', color: 'bg-blue-400', goodHigh: true },
  { key: 'word_of_mouth', label: 'Buzz', color: 'bg-violet-400', goodHigh: true },
  { key: 'churn_risk', label: 'Churn', color: 'bg-red-400', goodHigh: false },
  { key: 'adoption_rate', label: 'Adoption', color: 'bg-amber-400', goodHigh: true },
]

export const MARKET_METRIC_KEYS = MARKET_METRICS.map(m => m.key)

export function findMetricConfig(key) {
  return SOCIAL_METRICS.find(m => m.key === key) || MARKET_METRICS.find(m => m.key === key)
}

export function metricBarColor(key, value) {
  const val = value ?? 0.5
  const cfg = findMetricConfig(key)
  if (!cfg) return 'bg-slate-500'
  if (cfg.goodHigh) {
    if (val >= 0.7) return 'bg-emerald-400'
    if (val <= 0.3) return 'bg-red-400'
  } else {
    if (val >= 0.7) return 'bg-red-400'
    if (val <= 0.3) return 'bg-emerald-400'
  }
  return cfg.color
}
