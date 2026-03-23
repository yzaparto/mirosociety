<template>
  <div v-if="scorecard?.length">
    <h2 class="section-title">Scorecard</h2>
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="s in scorecard"
        :key="s.metric"
        :class="['border rounded-lg p-4 transition-colors', cardBg(s.rating)]"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-slate-500">{{ s.label }}</span>
          <span :class="['text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded', ratingColor(s.rating)]">
            {{ s.rating }}
          </span>
        </div>
        <div class="flex items-baseline gap-2">
          <span class="text-2xl font-bold font-mono">{{ s.value }}</span>
          <span class="text-xs text-slate-500">/100</span>
          <span :class="['text-xs ml-auto', trendColor(s.trend)]">
            {{ s.trend === 'up' ? '↑' : s.trend === 'down' ? '↓' : '→' }}
            <span class="text-slate-500 ml-0.5">from {{ s.start_value }}</span>
          </span>
        </div>
        <!-- Sparkline -->
        <div v-if="getSparkline(s.metric).length > 1" class="mt-2.5 h-6">
          <svg class="w-full h-full" preserveAspectRatio="none" :viewBox="`0 0 ${Math.max(getSparkline(s.metric).length - 1, getSparkline(s.metric).length + getForecastValues(s.metric).length - 1)} 1`">
            <polyline
              :points="sparklinePoints(s.metric)"
              fill="none"
              :stroke="sparklineStroke(s.rating)"
              stroke-width="0.06"
              stroke-linejoin="round"
              stroke-linecap="round"
              vector-effect="non-scaling-stroke"
              style="stroke-width: 1.5px"
            />
            <polyline
              v-if="forecastPoints(s.metric)"
              :points="forecastPoints(s.metric)"
              fill="none"
              stroke="#94a3b8"
              stroke-width="0.06"
              stroke-dasharray="0.15,0.1"
              stroke-linejoin="round"
              stroke-linecap="round"
              vector-effect="non-scaling-stroke"
              style="stroke-width: 1.5px"
              opacity="0.6"
            />
          </svg>
        </div>
        <p v-if="s.explanation" class="text-xs text-slate-500 mt-2 leading-relaxed">{{ s.explanation }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  scorecard: { type: Array, default: () => [] },
  metricsHistory: { type: Array, default: () => [] },
  forecasts: { type: Object, default: () => ({}) },
})

function getSparkline(metricKey) {
  if (!props.metricsHistory?.length) return []
  const hist = props.metricsHistory
  const sample = hist.length > 30
    ? hist.filter((_, i) => i % Math.ceil(hist.length / 30) === 0)
    : hist
  return sample.map(h => h[metricKey] ?? 0.5)
}

function sparklinePoints(metricKey) {
  const vals = getSparkline(metricKey)
  if (vals.length < 2) return ''
  return vals.map((v, i) => `${i},${1 - v}`).join(' ')
}

function getForecastValues(metricKey) {
  if (!props.forecasts?.projections) return []
  const proj = props.forecasts.projections.find(p => p.metric === metricKey)
  return proj ? proj.projected.slice(0, 10) : []
}

function forecastPoints(metricKey) {
  const historical = getSparkline(metricKey)
  const forecast = getForecastValues(metricKey)
  if (!forecast.length || historical.length < 2) return ''
  const startX = historical.length - 1
  const allPoints = [{ x: startX, y: historical[historical.length - 1] }]
  forecast.forEach((v, i) => allPoints.push({ x: startX + i + 1, y: v }))
  return allPoints.map(p => `${p.x},${1 - p.y}`).join(' ')
}

function sparklineStroke(rating) {
  if (rating === 'excellent' || rating === 'strong') return '#34d399'
  if (rating === 'moderate') return '#fbbf24'
  if (rating === 'weak') return '#fb923c'
  return '#f87171'
}

function ratingColor(rating) {
  if (rating === 'excellent' || rating === 'strong') return 'bg-emerald-500/20 text-emerald-600'
  if (rating === 'moderate') return 'bg-amber-500/20 text-amber-600'
  if (rating === 'weak') return 'bg-orange-500/20 text-orange-600'
  return 'bg-red-500/20 text-red-600'
}

function cardBg(rating) {
  if (rating === 'excellent' || rating === 'strong') return 'bg-emerald-50 border-emerald-200'
  if (rating === 'moderate') return 'bg-amber-50 border-amber-200'
  if (rating === 'weak') return 'bg-orange-50 border-orange-200'
  return 'bg-white border-gray-200'
}

function trendColor(trend) {
  if (trend === 'up') return 'text-emerald-600'
  if (trend === 'down') return 'text-red-600'
  return 'text-slate-500'
}
</script>
