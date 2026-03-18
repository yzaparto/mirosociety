<template>
  <div class="min-h-screen py-12">
    <div class="max-w-6xl mx-auto px-6">
      <router-link to="/" class="text-slate-500 hover:text-slate-300 text-sm">← Back to home</router-link>

      <div v-if="loading" class="text-center py-20 text-slate-400">Loading comparison...</div>

      <div v-else-if="data" class="mt-8 space-y-10">
        <h1 class="text-3xl font-bold">Timeline Comparison</h1>
        
        <!-- Side by side summaries -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-slate-900/60 border border-emerald-800/30 rounded-lg p-5">
            <div class="text-xs text-emerald-400 font-medium uppercase tracking-wider mb-2">Original Timeline</div>
            <h2 class="text-lg font-semibold mb-2">{{ data.source.report.executive_brief?.headline || data.source.report.meta?.world_name || data.source.report.title || 'Original' }}</h2>
            <p class="text-sm text-slate-400">{{ data.source.report.executive_brief?.summary || data.source.report.summary || '' }}</p>
            <div class="text-xs text-slate-500 mt-2">{{ data.source.final_day }} days simulated</div>
          </div>
          <div class="bg-slate-900/60 border border-blue-800/30 rounded-lg p-5">
            <div class="text-xs text-blue-400 font-medium uppercase tracking-wider mb-2">Forked Timeline</div>
            <h2 class="text-lg font-semibold mb-2">{{ data.fork.report.executive_brief?.headline || data.fork.report.meta?.world_name || data.fork.report.title || 'Fork' }}</h2>
            <p class="text-sm text-slate-400">{{ data.fork.report.executive_brief?.summary || data.fork.report.summary || '' }}</p>
            <div class="text-xs text-slate-500 mt-2">{{ data.fork.final_day }} days simulated</div>
          </div>
        </div>

        <!-- Metrics comparison -->
        <div v-if="comparisonMetrics.length">
          <h2 class="text-xl font-semibold mb-3">Metrics Comparison</h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div v-for="m in comparisonMetrics" :key="m.key" class="bg-slate-900/60 border border-slate-800/40 rounded-lg p-3">
              <div class="text-xs text-slate-500 mb-2">{{ m.label }}</div>
              <div class="flex gap-3 items-end">
                <div class="text-center">
                  <div class="text-sm font-mono text-emerald-400">{{ m.sourceEnd.toFixed(2) }}</div>
                  <div class="text-[10px] text-slate-600">Original</div>
                </div>
                <div class="text-slate-600">→</div>
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
        </div>

        <!-- Key moments side by side -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-if="sourceKeyMoments.length">
            <h2 class="text-lg font-semibold mb-3 text-emerald-400">Original — Key Moments</h2>
            <div class="border-l-2 border-emerald-800/50 pl-4 space-y-3">
              <div v-for="m in sourceKeyMoments" :key="m.day">
                <div class="text-xs text-emerald-500 font-medium">Day {{ m.day }}</div>
                <div class="text-sm font-medium">{{ m.title }}</div>
                <p class="text-xs text-slate-500">{{ m.description }}</p>
              </div>
            </div>
          </div>
          <div v-if="forkKeyMoments.length">
            <h2 class="text-lg font-semibold mb-3 text-blue-400">Fork — Key Moments</h2>
            <div class="border-l-2 border-blue-800/50 pl-4 space-y-3">
              <div v-for="m in forkKeyMoments" :key="m.day">
                <div class="text-xs text-blue-500 font-medium">Day {{ m.day }}</div>
                <div class="text-sm font-medium">{{ m.title }}</div>
                <p class="text-xs text-slate-500">{{ m.description }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Market analysis comparison (if both have it) -->
        <template v-if="data.source.report.market_analysis && data.fork.report.market_analysis">
          <h2 class="text-xl font-semibold mb-3">Market Outcome Comparison</h2>
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
        <div class="flex gap-3 pt-4">
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

const sourceKeyMoments = computed(() =>
  data.value?.source?.report?.narrative?.key_moments || data.value?.source?.report?.key_moments || []
)

const forkKeyMoments = computed(() =>
  data.value?.fork?.report?.narrative?.key_moments || data.value?.fork?.report?.key_moments || []
)

const comparisonMetrics = computed(() => {
  if (!data.value) return []
  const sm = data.value.source.metrics_history
  const fm = data.value.fork.metrics_history
  if (!sm?.length || !fm?.length) return []
  const sLast = sm[sm.length - 1]
  const fLast = fm[fm.length - 1]
  return METRICS
    .filter(m => !m.market || isMarket.value)
    .map(m => ({
      ...m,
      sourceEnd: sLast[m.key] ?? 0.5,
      forkEnd: fLast[m.key] ?? 0.5,
      delta: (fLast[m.key] ?? 0.5) - (sLast[m.key] ?? 0.5),
    }))
})

onMounted(async () => {
  try {
    data.value = await api.compare(route.params.id, route.params.forkId)
  } catch (e) {
    console.error('Failed to load comparison:', e)
  }
  loading.value = false
})
</script>
