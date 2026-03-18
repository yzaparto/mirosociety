<template>
  <div class="min-h-screen py-12">
    <div class="max-w-6xl mx-auto px-6">

      <div v-if="loading" class="text-center py-20">
        <div class="inline-flex items-center gap-3 bg-slate-900/60 border border-slate-800/40 rounded-lg px-5 py-3">
          <div class="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <span class="text-slate-300 text-sm">Loading comparison...</span>
        </div>
      </div>

      <div v-else-if="data" class="mt-4 space-y-10">
        <div class="text-center">
          <h1 class="text-3xl font-bold mb-2">Timeline Comparison</h1>
          <p class="text-sm text-slate-500">How did the fork diverge from the original?</p>
        </div>

        <!-- Side by side summaries with split metaphor -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-0 relative">
          <!-- Divider line -->
          <div class="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-slate-700/60 -translate-x-1/2 z-10">
            <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-slate-950 px-2 py-1 text-[9px] text-slate-600 uppercase tracking-wider">vs</div>
          </div>

          <div class="bg-slate-900/60 border border-emerald-800/30 rounded-l-lg md:rounded-r-none rounded-lg md:rounded-l-lg p-5">
            <div class="text-xs text-emerald-400 font-medium uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
              Original Timeline
            </div>
            <h2 class="text-lg font-semibold mb-2">{{ sourceHeadline }}</h2>
            <p class="text-sm text-slate-400 leading-relaxed">{{ sourceSummary }}</p>
            <div class="text-xs text-slate-500 mt-3">{{ data.source.final_day }} days simulated</div>
          </div>
          <div class="bg-slate-900/60 border border-blue-800/30 md:rounded-l-none rounded-lg md:rounded-r-lg p-5">
            <div class="text-xs text-blue-400 font-medium uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <div class="w-2 h-2 rounded-full bg-blue-400"></div>
              Forked Timeline
            </div>
            <h2 class="text-lg font-semibold mb-2">{{ forkHeadline }}</h2>
            <p class="text-sm text-slate-400 leading-relaxed">{{ forkSummary }}</p>
            <div class="text-xs text-slate-500 mt-3">{{ data.fork.final_day }} days simulated</div>
          </div>
        </div>

        <!-- Biggest Difference highlight -->
        <div v-if="biggestDiff" class="bg-slate-900/40 border border-slate-800/30 rounded-xl p-5 text-center">
          <div class="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Biggest Difference</div>
          <div class="text-2xl font-bold font-mono" :class="biggestDiff.delta > 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ biggestDiff.delta > 0 ? '+' : '' }}{{ (biggestDiff.delta * 100).toFixed(0) }}%
          </div>
          <div class="text-sm text-slate-400 mt-1">{{ biggestDiff.label }}</div>
        </div>

        <!-- Metrics comparison with sparklines -->
        <div v-if="comparisonMetrics.length">
          <h2 class="section-title">Metrics Comparison</h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div v-for="m in comparisonMetrics" :key="m.key" class="bg-slate-900/60 border border-slate-800/40 rounded-lg p-3">
              <div class="text-xs text-slate-500 mb-2">{{ m.label }}</div>

              <!-- Sparkline overlay -->
              <div v-if="m.sourceValues.length > 1" class="h-10 mb-2">
                <svg class="w-full h-full" preserveAspectRatio="none" :viewBox="`0 0 ${Math.max(m.sourceValues.length, m.forkValues.length) - 1} 1`">
                  <polyline
                    :points="sparkline(m.sourceValues)"
                    fill="none" stroke="#34d399" stroke-width="0.05"
                    stroke-linejoin="round" stroke-linecap="round"
                    vector-effect="non-scaling-stroke" style="stroke-width: 1.5px" stroke-opacity="0.7"
                  />
                  <polyline
                    :points="sparkline(m.forkValues)"
                    fill="none" stroke="#60a5fa" stroke-width="0.05"
                    stroke-linejoin="round" stroke-linecap="round"
                    vector-effect="non-scaling-stroke" style="stroke-width: 1.5px" stroke-opacity="0.7"
                  />
                </svg>
              </div>

              <div class="flex gap-3 items-end">
                <div class="text-center">
                  <div class="text-sm font-mono text-emerald-400">{{ m.sourceEnd.toFixed(2) }}</div>
                  <div class="text-[10px] text-slate-600">Original</div>
                </div>
                <div class="text-slate-600 text-xs">→</div>
                <div class="text-center">
                  <div class="text-sm font-mono text-blue-400">{{ m.forkEnd.toFixed(2) }}</div>
                  <div class="text-[10px] text-slate-600">Fork</div>
                </div>
              </div>
              <div :class="['text-[10px] mt-1 font-medium',
                m.delta > 0.05 ? 'text-emerald-500' : m.delta < -0.05 ? 'text-red-500' : 'text-slate-600']">
                {{ m.delta > 0 ? '+' : '' }}{{ (m.delta * 100).toFixed(0) }}%
              </div>
            </div>
          </div>
          <!-- Sparkline legend -->
          <div class="flex gap-4 mt-3 justify-center">
            <span class="text-[10px] text-slate-500 flex items-center gap-1"><span class="w-3 h-0.5 bg-emerald-400 rounded inline-block"></span> Original</span>
            <span class="text-[10px] text-slate-500 flex items-center gap-1"><span class="w-3 h-0.5 bg-blue-400 rounded inline-block"></span> Fork</span>
          </div>
        </div>

        <!-- Key moments side by side -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-if="sourceKeyMoments.length">
            <h2 class="text-lg font-semibold mb-3 text-emerald-400">Original Key Moments</h2>
            <div class="border-l-2 border-emerald-800/50 pl-4 space-y-3">
              <div v-for="m in sourceKeyMoments" :key="m.day">
                <div class="text-xs text-emerald-500 font-medium">Day {{ m.day }}</div>
                <div class="text-sm font-medium">{{ m.title }}</div>
                <p class="text-xs text-slate-500">{{ m.description }}</p>
              </div>
            </div>
          </div>
          <div v-if="forkKeyMoments.length">
            <h2 class="text-lg font-semibold mb-3 text-blue-400">Fork Key Moments</h2>
            <div class="border-l-2 border-blue-800/50 pl-4 space-y-3">
              <div v-for="m in forkKeyMoments" :key="m.day">
                <div class="text-xs text-blue-500 font-medium">Day {{ m.day }}</div>
                <div class="text-sm font-medium">{{ m.title }}</div>
                <p class="text-xs text-slate-500">{{ m.description }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Market analysis comparison -->
        <template v-if="data.source.report.market_analysis && data.fork.report.market_analysis">
          <h2 class="section-title">Market Outcome Comparison</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div v-if="data.source.report.market_analysis.aggregate" class="flex gap-2">
              <div class="flex-1 bg-emerald-950/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-emerald-400">{{ data.source.report.market_analysis.aggregate.adopted_pct }}%</div>
                <div class="text-[10px] text-slate-500">Adopted</div>
              </div>
              <div class="flex-1 bg-slate-800/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-slate-300">{{ data.source.report.market_analysis.aggregate.neutral_pct }}%</div>
                <div class="text-[10px] text-slate-500">Neutral</div>
              </div>
              <div class="flex-1 bg-red-950/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-red-400">{{ data.source.report.market_analysis.aggregate.rejected_pct }}%</div>
                <div class="text-[10px] text-slate-500">Rejected</div>
              </div>
            </div>
            <div v-if="data.fork.report.market_analysis.aggregate" class="flex gap-2">
              <div class="flex-1 bg-emerald-950/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-emerald-400">{{ data.fork.report.market_analysis.aggregate.adopted_pct }}%</div>
                <div class="text-[10px] text-slate-500">Adopted</div>
              </div>
              <div class="flex-1 bg-slate-800/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-slate-300">{{ data.fork.report.market_analysis.aggregate.neutral_pct }}%</div>
                <div class="text-[10px] text-slate-500">Neutral</div>
              </div>
              <div class="flex-1 bg-red-950/40 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-red-400">{{ data.fork.report.market_analysis.aggregate.rejected_pct }}%</div>
                <div class="text-[10px] text-slate-500">Rejected</div>
              </div>
            </div>
          </div>
        </template>

        <!-- Actions -->
        <div class="flex flex-wrap gap-3 pt-4 border-t border-slate-800/40">
          <router-link :to="`/report/${data.source.id}`" class="btn-secondary">View Original Report</router-link>
          <router-link :to="`/report/${data.fork.id}`" class="btn-secondary">View Fork Report</router-link>
          <router-link to="/" class="btn-secondary">Run New Simulation</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const data = ref(null)
const loading = ref(true)

const METRICS = [
  { key: 'stability', label: 'Stability' },
  { key: 'trust', label: 'Trust' },
  { key: 'conflict', label: 'Conflict' },
  { key: 'brand_sentiment', label: 'Brand Sentiment', market: true },
  { key: 'purchase_intent', label: 'Purchase Intent', market: true },
  { key: 'word_of_mouth', label: 'Word of Mouth', market: true },
  { key: 'churn_risk', label: 'Churn Risk', market: true },
  { key: 'adoption_rate', label: 'Adoption', market: true },
]

const isMarket = computed(() =>
  data.value?.source?.report?.market_analysis || data.value?.fork?.report?.market_analysis ||
  data.value?.source?.report?.segments?.length || data.value?.fork?.report?.segments?.length
)

const sourceHeadline = computed(() =>
  data.value?.source?.report?.executive_brief?.headline || data.value?.source?.report?.meta?.world_name || data.value?.source?.report?.title || 'Original'
)
const forkHeadline = computed(() =>
  data.value?.fork?.report?.executive_brief?.headline || data.value?.fork?.report?.meta?.world_name || data.value?.fork?.report?.title || 'Fork'
)
const sourceSummary = computed(() =>
  data.value?.source?.report?.executive_brief?.summary || data.value?.source?.report?.summary || ''
)
const forkSummary = computed(() =>
  data.value?.fork?.report?.executive_brief?.summary || data.value?.fork?.report?.summary || ''
)

const sourceKeyMoments = computed(() =>
  data.value?.source?.report?.narrative?.key_moments || data.value?.source?.report?.key_moments || []
)
const forkKeyMoments = computed(() =>
  data.value?.fork?.report?.narrative?.key_moments || data.value?.fork?.report?.key_moments || []
)

function sampleHistory(history) {
  if (!history?.length) return []
  return history.length > 30 ? history.filter((_, i) => i % Math.ceil(history.length / 30) === 0) : history
}

const comparisonMetrics = computed(() => {
  if (!data.value) return []
  const sm = data.value.source.metrics_history
  const fm = data.value.fork.metrics_history
  if (!sm?.length || !fm?.length) return []
  const sLast = sm[sm.length - 1]
  const fLast = fm[fm.length - 1]
  const sSampled = sampleHistory(sm)
  const fSampled = sampleHistory(fm)
  return METRICS
    .filter(m => !m.market || isMarket.value)
    .map(m => ({
      ...m,
      sourceEnd: sLast[m.key] ?? 0.5,
      forkEnd: fLast[m.key] ?? 0.5,
      delta: (fLast[m.key] ?? 0.5) - (sLast[m.key] ?? 0.5),
      sourceValues: sSampled.map(h => h[m.key] ?? 0.5),
      forkValues: fSampled.map(h => h[m.key] ?? 0.5),
    }))
})

const biggestDiff = computed(() => {
  if (!comparisonMetrics.value.length) return null
  return comparisonMetrics.value.reduce((max, m) =>
    Math.abs(m.delta) > Math.abs(max.delta) ? m : max
  , comparisonMetrics.value[0])
})

function sparkline(values) {
  if (values.length < 2) return ''
  const maxIdx = values.length - 1
  return values.map((v, i) => `${(i / maxIdx) * (values.length - 1)},${1 - v}`).join(' ')
}

onMounted(async () => {
  try {
    data.value = await api.compare(route.params.id, route.params.forkId)
  } catch (e) {
    console.error('Failed to load comparison:', e)
  }
  loading.value = false
})
</script>
