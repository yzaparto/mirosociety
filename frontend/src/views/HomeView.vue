<template>
  <div class="min-h-screen">
    <div class="max-w-5xl mx-auto px-6 py-16">
      <!-- Hero -->
      <div class="text-center mb-12">
        <h1 class="text-5xl font-bold tracking-tight mb-3">MiroSociety</h1>
        <div class="h-8 flex items-center justify-center">
          <Transition name="tagline" mode="out-in">
            <p :key="currentTagline" class="text-slate-500 text-lg">
              {{ currentTagline }}
            </p>
          </Transition>
        </div>
      </div>

      <!-- Input area -->
      <div class="max-w-2xl mx-auto space-y-4">
        <textarea
          v-model="rules"
          rows="4"
          class="w-full bg-slate-900 border border-slate-700/60 rounded-xl p-4 text-slate-100 placeholder-slate-500 focus:border-emerald-600/60 focus:ring-1 focus:ring-emerald-600/20 outline-none resize-none text-lg leading-relaxed transition-colors"
          placeholder="Describe your world or scenario..."
        ></textarea>

        <!-- Proposed Change (collapsible) -->
        <div class="border border-slate-700/60 rounded-xl overflow-hidden transition-all">
          <button
            @click="showProposedChange = !showProposedChange"
            class="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900/50 text-left text-sm text-slate-400 hover:text-slate-300 transition-colors"
          >
            <span>Proposed Change (optional)</span>
            <span :class="['text-slate-500 transition-transform duration-200', showProposedChange ? 'rotate-90' : '']">▶</span>
          </button>
          <Transition name="collapse">
            <div v-if="showProposedChange" class="p-4 border-t border-slate-700/40">
              <textarea
                v-model="proposedChange"
                rows="3"
                class="w-full bg-slate-900 border border-slate-700/60 rounded-lg p-3 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 outline-none resize-none text-sm transition-colors"
                placeholder="Describe a proposed change to test in the simulation..."
              ></textarea>
            </div>
          </Transition>
        </div>

        <!-- Customer Segments (collapsible) -->
        <div class="border border-slate-700/60 rounded-xl overflow-hidden">
          <button
            @click="showSegments = !showSegments"
            class="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900/50 text-left text-sm text-slate-400 hover:text-slate-300 transition-colors"
          >
            <span>Customer Segments (optional)</span>
            <span :class="['text-slate-500 transition-transform duration-200', showSegments ? 'rotate-90' : '']">▶</span>
          </button>
          <Transition name="collapse">
            <div v-if="showSegments" class="p-4 border-t border-slate-700/40 space-y-3">
              <div v-for="(seg, i) in segments" :key="i" class="flex gap-2 items-center">
                <input v-model="seg.name" placeholder="Segment name"
                  class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 text-sm outline-none focus:border-emerald-500 transition-colors" />
                <input v-model="seg.description" placeholder="Description"
                  class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 text-sm outline-none focus:border-emerald-500 transition-colors" />
                <button @click="removeSegment(i)" class="text-slate-500 hover:text-red-400 text-sm px-2 py-1 shrink-0 transition-colors">Remove</button>
              </div>
              <button @click="addSegment" class="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">+ Add segment</button>
            </div>
          </Transition>
        </div>

        <!-- Configuration: chip selectors -->
        <div class="space-y-3">
          <div>
            <label class="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 block">Population</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="opt in populationOptions"
                :key="opt"
                @click="population = opt"
                :class="[
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-all border active:scale-[0.97]',
                  population === opt
                    ? 'bg-emerald-600 border-emerald-500 text-white'
                    : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                ]"
              >
                {{ opt }}
              </button>
            </div>
          </div>
          <div>
            <label class="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 block">Duration</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="opt in durationOptions"
                :key="opt.value"
                @click="duration = opt.value"
                :class="[
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-all border active:scale-[0.97]',
                  duration === opt.value
                    ? 'bg-emerald-600 border-emerald-500 text-white'
                    : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                ]"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
        </div>

        <!-- Simulate button -->
        <button
          @click="startSimulation"
          :disabled="!rules.trim() || loading"
          :class="[
            'w-full py-3.5 rounded-xl font-semibold text-lg transition-all active:scale-[0.98]',
            rules.trim() && !loading
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
              : 'bg-slate-800 text-slate-500 cursor-not-allowed'
          ]"
        >
          {{ loading ? 'Starting...' : 'Simulate' }}
        </button>
      </div>

      <!-- Recent simulations -->
      <div v-if="recentSims.length" class="max-w-2xl mx-auto mt-8">
        <h3 class="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Recent</h3>
        <div class="flex flex-wrap gap-2">
          <router-link
            v-for="sim in recentSims"
            :key="sim.id"
            :to="`/report/${sim.id}`"
            class="text-[11px] px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700 transition-colors"
          >
            {{ sim.name || 'Unnamed' }}
          </router-link>
        </div>
      </div>

      <!-- Presets: tabbed interface -->
      <div class="mt-16">
        <div class="flex gap-1 mb-6">
          <button
            v-for="tab in presetTabs"
            :key="tab.id"
            @click="activePresetTab = tab.id"
            :class="[
              'text-sm font-medium px-4 py-2 rounded-lg transition-colors',
              activePresetTab === tab.id
                ? 'bg-slate-800 text-white'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
            ]"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <TransitionGroup name="list">
            <div
              v-for="preset in filteredPresets"
              :key="preset.id"
              @click="selectPreset(preset)"
              :class="[
                'card card-hover border-l-4 group',
                preset.proposed_change ? 'border-l-blue-500' : 'border-l-emerald-500'
              ]"
            >
              <div class="flex items-center gap-2 mb-1">
                <h3 class="font-semibold text-slate-100">{{ preset.name }}</h3>
                <span v-if="preset.proposed_change" class="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300 border border-blue-800/50">Market</span>
                <div class="flex-1"></div>
                <span class="text-[10px] text-slate-600 group-hover:text-emerald-400 transition-colors">Use this →</span>
              </div>
              <p class="text-sm text-slate-400 italic">{{ preset.teaser }}</p>
              <p v-if="preset.proposed_change" class="text-xs text-slate-500 mt-1.5 line-clamp-2">{{ preset.proposed_change }}</p>
            </div>
          </TransitionGroup>
        </div>

        <div class="text-center mt-6">
          <router-link to="/gallery" class="text-sm text-slate-500 hover:text-emerald-400 transition-colors">View Gallery →</router-link>
        </div>
      </div>

      <!-- How It Works -->
      <div class="mt-20 max-w-3xl mx-auto">
        <h2 class="text-sm font-medium text-slate-500 uppercase tracking-wider text-center mb-8">How It Works</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div v-for="(step, i) in howItWorks" :key="i" class="text-center">
            <div class="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 mx-auto mb-3">
              {{ step.number }}
            </div>
            <h3 class="font-medium text-sm text-slate-200 mb-1">{{ step.title }}</h3>
            <p class="text-xs text-slate-500 leading-relaxed">{{ step.description }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const rules = ref('')
const proposedChange = ref('')
const showProposedChange = ref(false)
const segments = ref([])
const showSegments = ref(false)
const population = ref(10)
const duration = ref(5)
const loading = ref(false)
const presets = ref([])
const activePresetTab = ref('all')
const recentSims = ref([])

const populationOptions = [2, 5, 10, 15, 20, 25, 30, 50]
const durationOptions = [
  { value: 1, label: '1d' }, { value: 2, label: '2d' }, { value: 5, label: '5d' },
  { value: 10, label: '10d' }, { value: 15, label: '15d' }, { value: 30, label: '30d' },
  { value: 90, label: '90d' }, { value: 180, label: '180d' }, { value: 365, label: '1y' },
]

const presetTabs = [
  { id: 'all', label: 'All Presets' },
  { id: 'social', label: 'Social Experiments' },
  { id: 'market', label: 'Market Simulations' },
]

const howItWorks = [
  { number: '01', title: 'Describe your world', description: 'Set the rules, constraints, or market conditions. Add customer segments for market sims.' },
  { number: '02', title: 'Watch it unfold', description: 'Citizens interact, form alliances, trade, and react in real time on an interactive map.' },
  { number: '03', title: 'Read the analysis', description: 'Get an executive report with scorecard, insights, risks, and actionable recommendations.' },
]

const filteredPresets = computed(() => {
  if (activePresetTab.value === 'social') return presets.value.filter(p => !p.proposed_change)
  if (activePresetTab.value === 'market') return presets.value.filter(p => !!p.proposed_change)
  return presets.value
})

const taglines = [
  'What happens when lying is impossible?',
  'No one can own private property...',
  'Everyone can read minds...',
  'Netflix raises prices by 40%...',
  'A beloved brand changes its logo...',
  'A startup launches at half the price...',
  'The CEO is caught in a scandal...',
  'Violence is legal but socially punished...',
]
const currentTagline = ref(taglines[0])
let taglineIdx = 0
let taglineTimer = null

function addSegment() { segments.value.push({ name: '', description: '' }) }
function removeSegment(i) { segments.value.splice(i, 1) }

function loadRecent() {
  try {
    const raw = localStorage.getItem('mirosociety_recent_sims')
    if (raw) recentSims.value = JSON.parse(raw).slice(0, 5)
  } catch { /* ignore */ }
}

function saveRecent(id, name) {
  try {
    const raw = localStorage.getItem('mirosociety_recent_sims')
    const list = raw ? JSON.parse(raw) : []
    const filtered = list.filter(s => s.id !== id)
    filtered.unshift({ id, name: name || 'Unnamed' })
    localStorage.setItem('mirosociety_recent_sims', JSON.stringify(filtered.slice(0, 10)))
  } catch { /* ignore */ }
}

onMounted(async () => {
  loadRecent()

  try {
    const data = await api.getPresets()
    presets.value = data.presets || []
  } catch (e) { console.error('Failed to load presets:', e) }

  taglineTimer = setInterval(() => {
    taglineIdx = (taglineIdx + 1) % taglines.length
    currentTagline.value = taglines[taglineIdx]
  }, 3500)
})

onUnmounted(() => { if (taglineTimer) clearInterval(taglineTimer) })

function selectPreset(preset) {
  rules.value = preset.rules
  if (preset.proposed_change) {
    proposedChange.value = preset.proposed_change
    showProposedChange.value = true
  } else { proposedChange.value = ''; showProposedChange.value = false }
  if (preset.segments) {
    segments.value = preset.segments.map(s => ({ name: s.name || '', description: s.description || '', count: s.count || null }))
    showSegments.value = true
  } else { segments.value = []; showSegments.value = false }
  if (preset.population) population.value = preset.population
  if (preset.duration_days) duration.value = preset.duration_days
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function startSimulation() {
  if (!rules.value.trim()) return
  loading.value = true
  try {
    const segs = segments.value.filter(s => (s.name || '').trim() || (s.description || '').trim())
    const data = await api.simulate(
      rules.value, population.value, duration.value,
      proposedChange.value.trim() || null,
      segs.length ? segs.map(s => ({ name: (s.name || '').trim(), description: (s.description || '').trim(), count: s.count || null })) : null
    )
    saveRecent(data.simulation_id, rules.value.slice(0, 40))
    router.push(`/simulation/${data.simulation_id}`)
  } catch (e) {
    console.error('Failed to start:', e)
    loading.value = false
  }
}
</script>

<style scoped>
.tagline-enter-active,
.tagline-leave-active {
  transition: all 0.4s ease;
}
.tagline-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.tagline-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
