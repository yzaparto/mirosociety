<template>
  <div v-if="scorecard?.length">
    <h2 class="text-xl font-semibold mb-4">Scorecard</h2>
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="s in scorecard"
        :key="s.metric"
        :class="['border rounded-lg p-4 transition-colors', cardBg(s.rating)]"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-slate-400">{{ s.label }}</span>
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
          <svg class="w-full h-full" preserveAspectRatio="none" :viewBox="`0 0 ${getSparkline(s.metric).length - 1} 1`">
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

function sparklineStroke(rating) {
  if (rating === 'excellent' || rating === 'strong') return '#34d399'
  if (rating === 'moderate') return '#fbbf24'
  if (rating === 'weak') return '#fb923c'
  return '#f87171'
}

function ratingColor(rating) {
  if (rating === 'excellent' || rating === 'strong') return 'bg-emerald-500/20 text-emerald-400'
  if (rating === 'moderate') return 'bg-amber-500/20 text-amber-400'
  if (rating === 'weak') return 'bg-orange-500/20 text-orange-400'
  return 'bg-red-500/20 text-red-400'
}

function cardBg(rating) {
  if (rating === 'excellent' || rating === 'strong') return 'bg-emerald-950/20 border-emerald-900/30'
  if (rating === 'moderate') return 'bg-amber-950/20 border-amber-900/30'
  if (rating === 'weak') return 'bg-orange-950/20 border-orange-900/30'
  return 'bg-slate-900/60 border-slate-800/40'
}

function trendColor(trend) {
  if (trend === 'up') return 'text-emerald-400'
  if (trend === 'down') return 'text-red-400'
  return 'text-slate-500'
}
</script>
