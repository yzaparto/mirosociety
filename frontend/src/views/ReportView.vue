<template>
  <div class="min-h-screen bg-[#fafafa] text-slate-800 py-12">
    <div class="max-w-4xl mx-auto px-6">

      <!-- Loading State -->
      <div v-if="loading" class="mt-16 space-y-6">
        <div class="text-center">
          <div class="inline-flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-5 py-3">
            <div class="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-slate-700 text-sm">Analyzing simulation results...</span>
          </div>
        </div>
        <div class="space-y-4 animate-pulse">
          <div class="h-20 bg-gray-50 rounded-xl"></div>
          <div class="grid grid-cols-3 gap-3">
            <div class="h-24 bg-gray-50 rounded-lg"></div>
            <div class="h-24 bg-gray-50 rounded-lg"></div>
            <div class="h-24 bg-gray-50 rounded-lg"></div>
          </div>
          <div class="h-32 bg-gray-50 rounded-lg"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="mt-16 text-center">
        <div class="bg-red-50 border border-red-200 rounded-lg p-6 inline-block">
          <p class="text-red-600 text-sm">{{ error }}</p>
          <button @click="loadReport" class="mt-3 text-xs text-slate-500 hover:text-slate-800 underline">Retry</button>
        </div>
      </div>

      <!-- Old Format Fallback -->
      <div v-else-if="report && isOldFormat" class="mt-8 space-y-10">
        <div>
          <h1 class="text-3xl font-bold mb-2">{{ report.title || report.world_name || 'Simulation Report' }}</h1>
          <p class="text-slate-500">{{ (report.rules || []).join(' · ') }}</p>
          <div class="flex gap-4 text-sm text-slate-500 mt-2">
            <span>{{ report.agent_count }} citizens</span>
            <span>{{ report.total_days }} days</span>
            <span>{{ report.total_actions }} events</span>
          </div>
        </div>
        <div>
          <h2 class="text-xl font-semibold mb-3">What Happened</h2>
          <p class="text-slate-700 leading-relaxed">{{ report.summary }}</p>
        </div>
        <div v-if="report.key_moments?.length">
          <h2 class="text-xl font-semibold mb-3">Key Moments</h2>
          <div class="border-l-2 border-gray-300 pl-4 space-y-4">
            <div v-for="m in report.key_moments" :key="m.day" class="relative">
              <div class="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 bg-emerald-500 rounded-full"></div>
              <div class="text-xs text-emerald-600 font-medium">Day {{ m.day }}</div>
              <div class="font-medium">{{ m.title }}</div>
              <p class="text-sm text-slate-500">{{ m.description }}</p>
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
            <svg v-if="brief.verdict === 'go'" class="w-24 h-24 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <svg v-else-if="brief.verdict === 'rethink'" class="w-24 h-24 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <svg v-else class="w-24 h-24 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
          </div>

          <div class="relative">
            <div class="flex items-start justify-between gap-4 mb-3">
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <span :class="['text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md',
                    brief.verdict === 'go' ? 'bg-emerald-100 text-emerald-600' :
                    brief.verdict === 'rethink' ? 'bg-red-100 text-red-600' :
                    'bg-amber-100 text-amber-600']">
                    {{ brief.verdict === 'go' ? 'Proceed' : brief.verdict === 'rethink' ? 'Rethink' : 'Caution' }}
                  </span>
                  <span class="text-xs text-slate-500 bg-gray-100 px-2 py-0.5 rounded">
                    {{ brief.confidence || 'medium' }} confidence
                  </span>
                </div>
                <h1 class="text-2xl font-bold">{{ brief.headline || meta.world_name || 'Analysis Complete' }}</h1>
              </div>
            </div>
            <p class="text-slate-700 leading-relaxed">{{ brief.summary }}</p>
            <div class="flex gap-4 text-sm text-slate-500 mt-4 pt-3 border-t border-gray-200">
              <span>{{ meta.agent_count }} agents</span>
              <span>{{ meta.total_days }} days</span>
              <span>{{ meta.total_actions?.toLocaleString() }} actions</span>
              <span>{{ (meta.rules || []).length }} rules</span>
            </div>
          </div>
        </div>

        <!-- 2. Scorecard (extracted component with sparklines) -->
        <ScorecardGrid :scorecard="report.scorecard" :metrics-history="report.metrics_history" :forecasts="report.forecasts || {}" />

        <!-- Causal Map -->
        <div v-if="report.causal_map?.length">
          <h2 class="section-title">Causal Relationships</h2>
          <p class="text-xs text-slate-500 mb-3">Statistically discovered cause-and-effect relationships between metrics (Granger causality)</p>
          <div class="space-y-2">
            <div v-for="(link, idx) in report.causal_map" :key="idx"
              class="flex items-center gap-3 bg-white border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition-colors">
              <div class="flex items-center gap-2 flex-1">
                <span class="text-sm font-medium text-slate-700">{{ link.cause_label }}</span>
                <span class="text-xs text-slate-400">→</span>
                <span class="text-sm font-medium text-slate-700">{{ link.effect_label }}</span>
              </div>
              <span class="text-xs text-slate-500">{{ link.lag }}-round lag</span>
              <span :class="['text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded',
                link.strength === 'strong' ? 'bg-emerald-100 text-emerald-600' :
                link.strength === 'moderate' ? 'bg-amber-100 text-amber-600' :
                'bg-gray-200 text-slate-500']">
                {{ link.strength }}
              </span>
            </div>
          </div>
        </div>

        <!-- Counterfactual Analysis -->
        <div v-if="report.counterfactuals?.length">
          <h2 class="section-title">What-If Analysis</h2>
          <p class="text-xs text-slate-500 mb-3">How key events changed the simulation trajectory vs. projected baseline</p>
          <div class="space-y-3">
            <div v-for="(cf, idx) in report.counterfactuals" :key="idx"
              class="bg-white border border-gray-200 rounded-lg p-4">
              <div class="text-sm font-medium text-slate-700 mb-2">{{ cf.event_description }}</div>
              <div class="flex flex-wrap gap-2">
                <div v-for="impact in cf.impacts" :key="impact.metric"
                  :class="['text-xs px-2 py-1 rounded-md',
                    impact.delta > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700']">
                  {{ impact.label }}: {{ impact.delta > 0 ? '+' : '' }}{{ (impact.delta * 100).toFixed(1) }}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Simulation Quality (Agent Coherence) -->
        <div v-if="report.agent_coherence?.total_agents">
          <h2 class="section-title">Simulation Quality</h2>
          <div class="bg-white border border-gray-200 rounded-lg p-5">
            <div class="flex items-center justify-between mb-3">
              <div>
                <span class="text-2xl font-bold font-mono">{{ report.agent_coherence.coherent_pct }}%</span>
                <span class="text-xs text-slate-500 ml-2">of agents behaved consistently with their personality</span>
              </div>
              <span :class="['text-[10px] font-semibold uppercase px-2 py-1 rounded',
                report.agent_coherence.coherent_pct >= 80 ? 'bg-emerald-100 text-emerald-600' :
                report.agent_coherence.coherent_pct >= 60 ? 'bg-amber-100 text-amber-600' :
                'bg-red-100 text-red-600']">
                {{ report.agent_coherence.coherent_pct >= 80 ? 'high quality' : report.agent_coherence.coherent_pct >= 60 ? 'moderate' : 'low quality' }}
              </span>
            </div>
            <div class="w-full bg-gray-100 rounded-full h-2 mb-3">
              <div :class="['h-full rounded-full',
                report.agent_coherence.coherent_pct >= 80 ? 'bg-emerald-500' :
                report.agent_coherence.coherent_pct >= 60 ? 'bg-amber-500' : 'bg-red-500']"
                :style="{ width: report.agent_coherence.coherent_pct + '%' }">
              </div>
            </div>
            <div v-if="report.agent_coherence.flagged_agents?.length" class="space-y-2 mt-3 pt-3 border-t border-gray-100">
              <div class="text-xs text-slate-500 font-medium">Flagged agents:</div>
              <div v-for="fa in report.agent_coherence.flagged_agents" :key="fa.agent_id"
                class="text-xs text-slate-500">
                <span class="text-red-600 font-medium">Agent {{ fa.agent_id }}</span>
                (coherence: {{ (fa.score * 100).toFixed(0) }}%)
                <span v-if="fa.contradictions.length"> — {{ fa.contradictions[0] }}</span>
              </div>
            </div>
          </div>
        </div>

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
              class="bg-white border border-gray-200 rounded-lg p-5">
              <div class="flex items-center justify-between mb-3">
                <h3 class="font-semibold">{{ seg.name }}</h3>
                <span :class="['text-sm font-mono px-2 py-0.5 rounded',
                  seg.adoption_pct >= 60 ? 'bg-emerald-100 text-emerald-600' :
                  seg.adoption_pct >= 30 ? 'bg-amber-100 text-amber-600' :
                  'bg-red-100 text-red-600']">
                  {{ seg.adoption_pct }}% adoption
                </span>
              </div>
              <div v-if="seg.funnel" class="mb-3">
                <div class="flex gap-1 h-5 rounded overflow-hidden bg-gray-100">
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
              <p v-if="seg.reaction" class="text-sm text-slate-500 leading-relaxed">{{ seg.reaction }}</p>
              <div v-if="seg.top_objection" class="mt-2 text-sm">
                <span class="text-red-600 text-xs font-medium">Top objection: </span>
                <span class="text-slate-500">{{ seg.top_objection }}</span>
              </div>
              <div v-if="seg.champion?.name" class="mt-2 text-sm">
                <span class="text-emerald-600 text-xs font-medium">Champion: </span>
                <span class="text-slate-500">{{ seg.champion.name }} — {{ seg.champion.why }}</span>
              </div>
              <p v-if="seg.representative_quote"
                class="mt-2 text-sm text-slate-500 italic border-l-2 border-emerald-200 pl-3">
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
              class="bg-white border border-gray-200 rounded-lg p-4 flex gap-4 hover:bg-gray-50 transition-colors">
              <div :class="['shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold',
                item.priority === 'high' ? 'bg-red-100 text-red-600' :
                item.priority === 'medium' ? 'bg-amber-100 text-amber-600' :
                'bg-gray-200 text-slate-500']">
                {{ idx + 1 }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium text-sm">{{ item.action }}</span>
                  <span :class="['text-[10px] uppercase px-1.5 py-0.5 rounded font-semibold',
                    item.priority === 'high' ? 'bg-red-100 text-red-600' :
                    item.priority === 'medium' ? 'bg-amber-100 text-amber-600' :
                    'bg-gray-200 text-slate-500']">
                    {{ item.priority }}
                  </span>
                </div>
                <p v-if="item.reasoning" class="text-xs text-slate-500 leading-relaxed">{{ item.reasoning }}</p>
                <p v-if="item.expected_impact" class="text-xs text-emerald-600/80 mt-1">Expected: {{ item.expected_impact }}</p>
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
                class="flex items-start gap-3 bg-white border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition-colors">
                <span :class="['text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded shrink-0 mt-0.5',
                  risk.severity === 'high' ? 'bg-red-100 text-red-600' :
                  risk.severity === 'medium' ? 'bg-amber-100 text-amber-600' :
                  'bg-gray-200 text-slate-500']">
                  {{ risk.severity }}
                </span>
                <span class="text-sm text-slate-700">{{ risk.risk }}</span>
              </div>
            </div>
          </div>
          <div v-if="report.second_order_effects?.length">
            <h2 class="section-title">Second-Order Effects</h2>
            <ul class="space-y-2">
              <li v-for="(effect, i) in report.second_order_effects" :key="i" class="flex gap-2 text-sm">
                <span class="text-blue-600 shrink-0">↪</span>
                <span class="text-slate-500">{{ effect }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- 7. Evidence Trail -->
        <div v-if="report.narrative || report.metrics_history?.length > 1">
          <button @click="showEvidence = !showEvidence"
            class="flex items-center gap-2 text-lg font-semibold mb-4 hover:text-emerald-600 transition-colors group">
            <span :class="['text-xs transition-transform duration-200 text-slate-400 group-hover:text-emerald-600', showEvidence ? 'rotate-90' : '']">▶</span>
            Evidence Trail
            <span class="text-xs text-slate-400 font-normal ml-1">{{ showEvidence ? 'Hide' : 'Show' }}</span>
          </button>
          <Transition name="collapse">
            <div v-if="showEvidence" class="space-y-6">
              <div v-if="report.narrative?.summary">
                <h3 class="text-sm font-medium text-slate-500 mb-2">Narrative Summary</h3>
                <p class="text-sm text-slate-700 leading-relaxed">{{ report.narrative.summary }}</p>
              </div>
              <div v-if="report.narrative?.key_moments?.length">
                <h3 class="text-sm font-medium text-slate-500 mb-2">Key Moments</h3>
                <div class="border-l-2 border-gray-200 pl-4 space-y-3">
                  <div v-for="m in report.narrative.key_moments" :key="m.day" class="relative">
                    <div class="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 bg-emerald-500 rounded-full"></div>
                    <div class="text-xs text-emerald-600 font-medium">Day {{ m.day }}</div>
                    <div class="text-sm font-medium">{{ m.title }}</div>
                    <p class="text-xs text-slate-500">{{ m.description }}</p>
                  </div>
                </div>
              </div>
              <div v-if="report.metrics_history?.length > 1">
                <h3 class="text-sm font-medium text-slate-500 mb-2">Metrics Trajectory</h3>
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div v-for="metric in displayMetrics" :key="metric.key"
                    class="bg-white border border-gray-200 rounded-lg p-3">
                    <div class="text-xs text-slate-500 mb-1">{{ metric.label }}</div>
                    <div class="flex items-end gap-[2px] h-8">
                      <div v-for="(val, i) in metric.values" :key="i"
                        :class="['flex-1 rounded-sm min-w-[2px]', metric.color]"
                        :style="{ height: (val * 100) + '%', opacity: 0.4 + (i / metric.values.length) * 0.6 }">
                      </div>
                    </div>
                    <div class="flex justify-between text-[10px] text-slate-400 mt-1">
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
        <div class="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200/60 rounded-xl p-8 text-center">
          <div class="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center mx-auto mb-3">
            <svg class="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
          </div>
          <h3 class="font-semibold text-lg mb-1">Explore alternate timelines</h3>
          <p class="text-sm text-slate-500 mb-5">Fork this simulation to test different scenarios from the same starting point.</p>
          <router-link
            :to="`/simulation/${route.params.id}`"
            class="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors active:scale-[0.97] shadow-sm"
          >
            Fork from this simulation →
          </router-link>
        </div>

        <!-- 9. Footer Actions -->
        <div class="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
          <router-link to="/" class="btn-primary text-sm">Run Again</router-link>
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
  go: 'bg-emerald-50 border-emerald-200',
  caution: 'bg-amber-50 border-amber-200',
  rethink: 'bg-red-50 border-red-200',
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
  document.title = title
  window.print()
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
