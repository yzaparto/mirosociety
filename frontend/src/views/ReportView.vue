<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 py-12">
    <div class="max-w-4xl mx-auto px-6">

      <!-- Loading State -->
      <div v-if="loading" class="mt-16 space-y-6">
        <div class="text-center">
          <div class="inline-flex items-center gap-3 bg-slate-900/60 border border-slate-800/40 rounded-lg px-5 py-3">
            <div class="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-slate-300 text-sm">Analyzing simulation results...</span>
          </div>
        </div>
        <div class="space-y-4 animate-pulse">
          <div class="h-20 bg-slate-900/40 rounded-xl"></div>
          <div class="grid grid-cols-3 gap-3">
            <div class="h-24 bg-slate-900/40 rounded-lg"></div>
            <div class="h-24 bg-slate-900/40 rounded-lg"></div>
            <div class="h-24 bg-slate-900/40 rounded-lg"></div>
          </div>
          <div class="h-32 bg-slate-900/40 rounded-lg"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="mt-16 text-center">
        <div class="bg-red-950/40 border border-red-800/40 rounded-lg p-6 inline-block">
          <p class="text-red-400 text-sm">{{ error }}</p>
          <button @click="loadReport" class="mt-3 text-xs text-slate-400 hover:text-slate-200 underline">Retry</button>
        </div>
      </div>

      <!-- Old Format Fallback -->
      <div v-else-if="report && isOldFormat" class="mt-8 space-y-10">
        <div>
          <h1 class="text-3xl font-bold mb-2">{{ report.title || report.world_name || 'Simulation Report' }}</h1>
          <p class="text-slate-400">{{ (report.rules || []).join(' · ') }}</p>
          <div class="flex gap-4 text-sm text-slate-500 mt-2">
            <span>{{ report.agent_count }} citizens</span>
            <span>{{ report.total_days }} days</span>
            <span>{{ report.total_actions }} events</span>
          </div>
        </div>
        <div>
          <h2 class="text-xl font-semibold mb-3">What Happened</h2>
          <p class="text-slate-300 leading-relaxed">{{ report.summary }}</p>
        </div>
        <div v-if="report.key_moments?.length">
          <h2 class="text-xl font-semibold mb-3">Key Moments</h2>
          <div class="border-l-2 border-slate-700 pl-4 space-y-4">
            <div v-for="m in report.key_moments" :key="m.day" class="relative">
              <div class="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 bg-emerald-500 rounded-full"></div>
              <div class="text-xs text-emerald-400 font-medium">Day {{ m.day }}</div>
              <div class="font-medium">{{ m.title }}</div>
              <p class="text-sm text-slate-400">{{ m.description }}</p>
            </div>
          </div>
        </div>
        <div class="flex gap-3 pt-4">
          <router-link to="/" class="btn-secondary">Run Again</router-link>
          <button @click="copyLink" class="btn-secondary">{{ copied ? 'Copied!' : 'Share Link' }}</button>
        </div>
      </div>

      <!-- New Analyst Report -->
      <div v-else-if="report" class="mt-8 space-y-10">

        <!-- 1. Executive Brief with verdict hero -->
        <div :class="['rounded-xl p-6 border relative overflow-hidden', verdictStyles[brief.verdict] || verdictStyles.caution]">
          <!-- Verdict icon -->
          <div class="absolute top-4 right-4 opacity-10">
            <svg v-if="brief.verdict === 'go'" class="w-24 h-24 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <svg v-else-if="brief.verdict === 'rethink'" class="w-24 h-24 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <svg v-else class="w-24 h-24 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
          </div>

          <div class="relative">
            <div class="flex items-start justify-between gap-4 mb-3">
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <span :class="['text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md',
                    brief.verdict === 'go' ? 'bg-emerald-500/20 text-emerald-400' :
                    brief.verdict === 'rethink' ? 'bg-red-500/20 text-red-400' :
                    'bg-amber-500/20 text-amber-400']">
                    {{ brief.verdict === 'go' ? 'Proceed' : brief.verdict === 'rethink' ? 'Rethink' : 'Caution' }}
                  </span>
                  <span class="text-xs text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded">
                    {{ brief.confidence || 'medium' }} confidence
                  </span>
                </div>
                <h1 class="text-2xl font-bold">{{ brief.headline || meta.world_name || 'Analysis Complete' }}</h1>
              </div>
            </div>
            <p class="text-slate-300 leading-relaxed">{{ brief.summary }}</p>
            <div class="flex gap-4 text-sm text-slate-500 mt-4 pt-3 border-t border-slate-800/40">
              <span>{{ meta.agent_count }} agents</span>
              <span>{{ meta.total_days }} days</span>
              <span>{{ meta.total_actions?.toLocaleString() }} actions</span>
              <span>{{ (meta.rules || []).length }} rules</span>
            </div>
          </div>
        </div>

        <!-- 2. Scorecard (extracted component with sparklines) -->
        <ScorecardGrid :scorecard="report.scorecard" :metrics-history="report.metrics_history" />

        <!-- 3. Key Insights -->
        <div v-if="report.insights?.length">
          <h2 class="section-title">Key Insights</h2>
          <div class="space-y-3">
            <InsightCard v-for="(insight, idx) in report.insights" :key="idx" :insight="insight" />
          </div>
        </div>

        <!-- 4. Segment Deep-Dive -->
        <div v-if="report.segments?.length">
          <h2 class="section-title">Segment Deep-Dive</h2>
          <div class="space-y-4">
            <div v-for="seg in report.segments" :key="seg.name"
              class="bg-slate-900/60 border border-slate-800/40 rounded-lg p-5">
              <div class="flex items-center justify-between mb-3">
                <h3 class="font-semibold">{{ seg.name }}</h3>
                <span :class="['text-sm font-mono px-2 py-0.5 rounded',
                  seg.adoption_pct >= 60 ? 'bg-emerald-900/50 text-emerald-400' :
                  seg.adoption_pct >= 30 ? 'bg-amber-900/50 text-amber-400' :
                  'bg-red-900/50 text-red-400']">
                  {{ seg.adoption_pct }}% adoption
                </span>
              </div>
              <div v-if="seg.funnel" class="mb-3">
                <div class="flex gap-1 h-5 rounded overflow-hidden bg-slate-800/40">
                  <div v-for="stage in funnelStages" :key="stage.key"
                    :class="['h-full transition-all', stage.color]"
                    :style="{ width: funnelWidth(seg.funnel, stage.key) + '%' }"
                    :title="`${stage.label}: ${seg.funnel[stage.key]}`">
                  </div>
                </div>
                <div class="flex gap-3 mt-1.5">
                  <span v-for="stage in funnelStages" :key="stage.key" class="text-[10px] text-slate-500 flex items-center gap-1">
                    <span :class="['w-2 h-2 rounded-sm inline-block', stage.color]"></span>
                    {{ stage.label }}: {{ seg.funnel[stage.key] }}
                  </span>
                </div>
              </div>
              <p v-if="seg.reaction" class="text-sm text-slate-400 leading-relaxed">{{ seg.reaction }}</p>
              <div v-if="seg.top_objection" class="mt-2 text-sm">
                <span class="text-red-400 text-xs font-medium">Top objection: </span>
                <span class="text-slate-400">{{ seg.top_objection }}</span>
              </div>
              <div v-if="seg.champion?.name" class="mt-2 text-sm">
                <span class="text-emerald-400 text-xs font-medium">Champion: </span>
                <span class="text-slate-400">{{ seg.champion.name }} — {{ seg.champion.why }}</span>
              </div>
              <p v-if="seg.representative_quote"
                class="mt-2 text-sm text-slate-500 italic border-l-2 border-slate-700 pl-3">
                "{{ seg.representative_quote }}"
              </p>
            </div>
          </div>
        </div>

        <!-- 5. Action Items -->
        <div v-if="report.action_items?.length">
          <h2 class="section-title">Action Items</h2>
          <div class="space-y-3">
            <div v-for="(item, idx) in report.action_items" :key="idx"
              class="bg-slate-900/60 border border-slate-800/40 rounded-lg p-4 flex gap-4 hover:bg-slate-900/80 transition-colors">
              <div :class="['shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold',
                item.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                item.priority === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                'bg-slate-700/50 text-slate-400']">
                {{ idx + 1 }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium text-sm">{{ item.action }}</span>
                  <span :class="['text-[10px] uppercase px-1.5 py-0.5 rounded font-semibold',
                    item.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                    item.priority === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                    'bg-slate-700/50 text-slate-400']">
                    {{ item.priority }}
                  </span>
                </div>
                <p v-if="item.reasoning" class="text-xs text-slate-500 leading-relaxed">{{ item.reasoning }}</p>
                <p v-if="item.expected_impact" class="text-xs text-emerald-500/80 mt-1">Expected: {{ item.expected_impact }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 6. Risks & Effects -->
        <div v-if="report.risks?.length || report.second_order_effects?.length" class="space-y-6">
          <div v-if="report.risks?.length">
            <h2 class="section-title">Risks</h2>
            <div class="space-y-2">
              <div v-for="(risk, idx) in report.risks" :key="idx"
                class="flex items-start gap-3 bg-slate-900/60 border border-slate-800/40 rounded-lg p-3 hover:bg-slate-900/80 transition-colors">
                <span :class="['text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded shrink-0 mt-0.5',
                  risk.severity === 'high' ? 'bg-red-500/20 text-red-400' :
                  risk.severity === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                  'bg-slate-700/50 text-slate-400']">
                  {{ risk.severity }}
                </span>
                <span class="text-sm text-slate-300">{{ risk.risk }}</span>
              </div>
            </div>
          </div>
          <div v-if="report.second_order_effects?.length">
            <h2 class="section-title">Second-Order Effects</h2>
            <ul class="space-y-2">
              <li v-for="(effect, i) in report.second_order_effects" :key="i" class="flex gap-2 text-sm">
                <span class="text-blue-400 shrink-0">↪</span>
                <span class="text-slate-400">{{ effect }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- 7. Evidence Trail -->
        <div v-if="report.narrative || report.metrics_history?.length > 1">
          <button @click="showEvidence = !showEvidence"
            class="flex items-center gap-2 text-xl font-semibold mb-4 hover:text-emerald-400 transition-colors">
            <span :class="['text-sm transition-transform duration-200', showEvidence ? 'rotate-90' : '']">▶</span>
            Evidence Trail
          </button>
          <Transition name="collapse">
            <div v-if="showEvidence" class="space-y-6">
              <div v-if="report.narrative?.summary">
                <h3 class="text-sm font-medium text-slate-400 mb-2">Narrative Summary</h3>
                <p class="text-sm text-slate-300 leading-relaxed">{{ report.narrative.summary }}</p>
              </div>
              <div v-if="report.narrative?.key_moments?.length">
                <h3 class="text-sm font-medium text-slate-400 mb-2">Key Moments</h3>
                <div class="border-l-2 border-slate-700 pl-4 space-y-3">
                  <div v-for="m in report.narrative.key_moments" :key="m.day" class="relative">
                    <div class="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 bg-emerald-500 rounded-full"></div>
                    <div class="text-xs text-emerald-400 font-medium">Day {{ m.day }}</div>
                    <div class="text-sm font-medium">{{ m.title }}</div>
                    <p class="text-xs text-slate-400">{{ m.description }}</p>
                  </div>
                </div>
              </div>
              <div v-if="report.metrics_history?.length > 1">
                <h3 class="text-sm font-medium text-slate-400 mb-2">Metrics Trajectory</h3>
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div v-for="metric in displayMetrics" :key="metric.key"
                    class="bg-slate-900/60 border border-slate-800/40 rounded-lg p-3">
                    <div class="text-xs text-slate-500 mb-1">{{ metric.label }}</div>
                    <div class="flex items-end gap-[2px] h-8">
                      <div v-for="(val, i) in metric.values" :key="i"
                        :class="['flex-1 rounded-sm min-w-[2px]', metric.color]"
                        :style="{ height: (val * 100) + '%', opacity: 0.4 + (i / metric.values.length) * 0.6 }">
                      </div>
                    </div>
                    <div class="flex justify-between text-[10px] text-slate-600 mt-1">
                      <span>{{ metric.values[0]?.toFixed(2) }}</span>
                      <span>{{ metric.values[metric.values.length - 1]?.toFixed(2) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- 8. Fork CTA -->
        <div class="bg-slate-900/60 border border-slate-800/40 rounded-xl p-6 text-center">
          <h3 class="font-semibold text-lg mb-1">Explore alternate timelines</h3>
          <p class="text-sm text-slate-400 mb-4">Fork this simulation to test different scenarios from the same starting point.</p>
          <router-link
            :to="`/simulation/${route.params.id}`"
            class="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors active:scale-[0.97]"
          >
            Fork from this simulation
          </router-link>
        </div>

        <!-- 9. Footer Actions -->
        <div class="flex flex-wrap gap-3 pt-4 border-t border-slate-800/40">
          <router-link to="/" class="btn-secondary">Run Again</router-link>
          <button @click="copyLink" class="btn-secondary">{{ copied ? 'Copied!' : 'Share Link' }}</button>
          <button @click="doPublish" :disabled="published" class="btn-secondary">
            {{ published ? 'Published' : 'Publish to Gallery' }}
          </button>
          <button @click="copyMarkdown" class="btn-secondary">{{ copiedMd ? 'Copied!' : 'Copy as Markdown' }}</button>
          <button @click="downloadPdf" class="btn-secondary inline-flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            Download PDF
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import ScorecardGrid from '../components/ScorecardGrid.vue'
import InsightCard from '../components/InsightCard.vue'

const route = useRoute()
const report = ref(null)
const loading = ref(true)
const error = ref(null)
const copied = ref(false)
const copiedMd = ref(false)
const published = ref(false)
const showEvidence = ref(false)

const verdictStyles = {
  go: 'bg-emerald-950/40 border-emerald-800/40',
  caution: 'bg-amber-950/40 border-amber-800/40',
  rethink: 'bg-red-950/40 border-red-800/40',
}

const funnelStages = [
  { key: 'aware', label: 'Aware', color: 'bg-slate-500' },
  { key: 'interested', label: 'Interested', color: 'bg-blue-500' },
  { key: 'tried', label: 'Tried', color: 'bg-amber-500' },
  { key: 'adopted', label: 'Adopted', color: 'bg-emerald-500' },
  { key: 'churned', label: 'Churned', color: 'bg-red-500' },
]

const isOldFormat = computed(() => !report.value?.executive_brief && (report.value?.title || report.value?.summary))
const brief = computed(() => report.value?.executive_brief || {})
const meta = computed(() => report.value?.meta || {})

const METRIC_CONFIG = [
  { key: 'stability', label: 'Stability', color: 'bg-emerald-500' },
  { key: 'trust', label: 'Trust', color: 'bg-blue-500' },
  { key: 'conflict', label: 'Conflict', color: 'bg-red-500' },
  { key: 'freedom', label: 'Freedom', color: 'bg-amber-500' },
  { key: 'brand_sentiment', label: 'Brand Sentiment', color: 'bg-emerald-400', market: true },
  { key: 'purchase_intent', label: 'Purchase Intent', color: 'bg-blue-400', market: true },
  { key: 'word_of_mouth', label: 'Word of Mouth', color: 'bg-violet-400', market: true },
  { key: 'churn_risk', label: 'Churn Risk', color: 'bg-red-400', market: true },
  { key: 'adoption_rate', label: 'Adoption Rate', color: 'bg-amber-400', market: true },
]

const isMarketSim = computed(() => {
  const sc = report.value?.scorecard || []
  return sc.some(s => ['brand_sentiment', 'purchase_intent', 'word_of_mouth', 'churn_risk', 'adoption_rate'].includes(s.metric))
})

const displayMetrics = computed(() => {
  if (!report.value?.metrics_history?.length) return []
  const history = report.value.metrics_history
  const sample = history.length > 30 ? history.filter((_, i) => i % Math.ceil(history.length / 30) === 0) : history
  return METRIC_CONFIG
    .filter(m => !m.market || isMarketSim.value)
    .map(m => ({ ...m, values: sample.map(h => h[m.key] ?? 0.5) }))
})

function funnelWidth(funnel, key) {
  const val = funnel[key] || 0
  if (val === 0) return 0
  const max = funnel.aware || 1
  return Math.max(2, (val / max) * 100)
}

async function loadReport() {
  loading.value = true
  error.value = null
  try { report.value = await api.pollReport(route.params.id) }
  catch (e) { error.value = e.message || 'Failed to load report' }
  loading.value = false
}

onMounted(loadReport)

async function doPublish() {
  try { await api.publish(route.params.id); published.value = true }
  catch (e) { console.error('Failed to publish:', e) }
}

function copyLink() {
  navigator.clipboard.writeText(window.location.href)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function downloadPdf() {
  const title = brief.value?.headline || meta.value?.world_name || 'Simulation Report'
  const style = document.createElement('style')
  style.textContent = `
    @media print {
      body * { visibility: hidden; }
      .max-w-4xl, .max-w-4xl * { visibility: visible; }
      .max-w-4xl { position: absolute; left: 0; top: 0; width: 100%; max-width: 100%; padding: 20px; }
      .btn-secondary, .btn-secondary *, nav, nav * { display: none !important; }
      @page { margin: 1cm; size: A4; }
      .bg-slate-950 { background: white !important; color: black !important; }
      .text-slate-200, .text-slate-300, .text-slate-400 { color: #333 !important; }
      .text-slate-500, .text-slate-600 { color: #666 !important; }
      .border-slate-800\\/40 { border-color: #ddd !important; }
      .bg-slate-900\\/60 { background: #f5f5f5 !important; }
    }
  `
  document.head.appendChild(style)
  document.title = title
  window.print()
  document.head.removeChild(style)
  document.title = 'MiroSociety'
}

function copyMarkdown() {
  if (!report.value) return
  const b = brief.value
  const m = meta.value
  let md = `# ${b.headline || m.world_name || 'Report'}\n\n`
  md += `**Verdict:** ${b.verdict || 'N/A'} | **Confidence:** ${b.confidence || 'N/A'}\n\n`
  md += `${b.summary || ''}\n\n`
  md += `**Stats:** ${m.agent_count} agents, ${m.total_days} days, ${m.total_actions} actions\n\n`

  if (report.value.insights?.length) {
    md += `## Key Insights\n\n`
    for (const i of report.value.insights) {
      md += `- **[${i.type}] ${i.title}:** ${i.description}\n`
    }
    md += '\n'
  }

  if (report.value.action_items?.length) {
    md += `## Action Items\n\n`
    for (const a of report.value.action_items) {
      md += `${a.priority === 'high' ? '!' : '-'} ${a.action}\n`
    }
    md += '\n'
  }

  navigator.clipboard.writeText(md)
  copiedMd.value = true
  setTimeout(() => { copiedMd.value = false }, 2000)
}
</script>

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
