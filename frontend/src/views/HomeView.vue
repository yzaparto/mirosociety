<template>
  <div class="h-screen relative overflow-hidden bg-[#fafafa]">
    <AgentSwarmCanvas />

    <div class="absolute inset-0 z-20 overflow-y-auto pointer-events-none">
      <div class="min-h-full flex items-center justify-center py-6 px-6">
        <div class="w-full max-w-4xl pointer-events-auto">
          <!-- Header -->
          <div class="text-center mb-5">
            <h1 class="text-2xl font-medium text-slate-900 tracking-tight mb-1">MiroSociety</h1>
            <p class="text-slate-500 text-sm">Write the rules. Watch what emerges.</p>
          </div>

          <div class="bg-white/92 backdrop-blur-md rounded-2xl shadow-xl shadow-black/8 border border-gray-200/60 overflow-hidden">
            <div class="flex flex-col md:flex-row">

              <!-- LEFT: Scenario input -->
              <div class="flex-1 p-6 space-y-4">
                <textarea
                  v-model="rules"
                  rows="4"
                  class="w-full bg-white border border-gray-200 rounded-xl p-4 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none resize-none text-sm leading-relaxed transition-all"
                  placeholder="Describe your world or scenario..."
                ></textarea>

                <!-- Preset chips -->
                <div v-if="presets.length" class="flex flex-wrap gap-1.5">
                  <button
                    v-for="preset in visiblePresets"
                    :key="preset.id"
                    @click="selectPreset(preset)"
                    class="text-[11px] px-2.5 py-1.5 rounded-lg border transition-all active:scale-[0.97]"
                    :class="rules === preset.rules
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'bg-gray-50/80 border-gray-200 text-slate-500 hover:border-gray-300 hover:text-slate-700'"
                  >
                    {{ preset.name }}
                  </button>
                </div>

                <!-- Proposed Change -->
                <div v-if="showProposedChange || proposedChange" class="space-y-1.5">
                  <label class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Proposed Change</label>
                  <textarea
                    v-model="proposedChange"
                    rows="2"
                    class="w-full bg-white border border-gray-200 rounded-lg p-3 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 outline-none resize-none text-sm transition-all"
                    placeholder="Describe a proposed change to test..."
                  ></textarea>
                </div>

                <!-- City Demographics -->
                <div v-if="showCity || city" class="space-y-1.5">
                  <label class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Base on Real City</label>
                  <input
                    v-model="city"
                    type="text"
                    class="w-full bg-white border border-gray-200 rounded-lg p-3 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 outline-none text-sm transition-all"
                    placeholder="e.g. San Francisco, CA"
                  />
                  <p class="text-[10px] text-slate-400">Agents will reflect real demographics from US Census data</p>
                </div>

                <!-- Customer Segments -->
                <div v-if="showSegments || segments.length" class="space-y-2">
                  <label class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Customer Segments</label>
                  <div class="space-y-1.5">
                    <div v-for="(seg, i) in segments" :key="i" class="flex gap-1.5 items-center">
                      <input v-model="seg.name" placeholder="Name"
                        class="w-36 bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-slate-900 placeholder-slate-400 text-xs outline-none focus:border-emerald-500 transition-colors" />
                      <input v-model="seg.description" placeholder="Description"
                        class="flex-1 bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-slate-900 placeholder-slate-400 text-xs outline-none focus:border-emerald-500 transition-colors" />
                      <button @click="removeSegment(i)" class="text-slate-300 hover:text-red-400 transition-colors shrink-0">
                        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                      </button>
                    </div>
                  </div>
                  <button @click="addSegment" class="text-xs text-emerald-600 hover:text-emerald-500 transition-colors">+ Add segment</button>
                </div>
              </div>

              <!-- DIVIDER -->
              <div class="hidden md:block w-px bg-gray-200/60 my-4"></div>
              <div class="md:hidden h-px bg-gray-200/60 mx-4"></div>

              <!-- RIGHT: Config + CTA -->
              <div class="w-full md:w-72 p-6 space-y-5 shrink-0">
                <div>
                  <label class="text-[10px] text-slate-400 uppercase tracking-wider mb-2 block font-medium">Population</label>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="opt in populationOptions"
                      :key="opt"
                      @click="population = opt"
                      :class="[
                        'px-2.5 py-1 rounded-lg text-xs font-medium transition-all border active:scale-[0.97]',
                        population === opt
                          ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                          : 'bg-gray-50/80 border-gray-200 text-slate-500 hover:border-gray-300 hover:text-slate-700'
                      ]"
                    >
                      {{ opt }}
                    </button>
                  </div>
                </div>

                <div>
                  <label class="text-[10px] text-slate-400 uppercase tracking-wider mb-2 block font-medium">Duration</label>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="opt in durationOptions"
                      :key="opt.value"
                      @click="duration = opt.value"
                      :class="[
                        'px-2.5 py-1 rounded-lg text-xs font-medium transition-all border active:scale-[0.97]',
                        duration === opt.value
                          ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                          : 'bg-gray-50/80 border-gray-200 text-slate-500 hover:border-gray-300 hover:text-slate-700'
                      ]"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </div>

                <!-- Optional toggles -->
                <div class="space-y-1.5">
                  <button
                    v-if="!showProposedChange && !proposedChange"
                    @click="showProposedChange = true"
                    class="w-full text-left text-xs text-slate-400 hover:text-slate-600 transition-colors py-1"
                  >
                    + Add proposed change
                  </button>
                  <button
                    v-if="!showSegments && !segments.length"
                    @click="showSegments = true; if (!segments.length) addSegment()"
                    class="w-full text-left text-xs text-slate-400 hover:text-slate-600 transition-colors py-1"
                  >
                    + Add customer segments
                  </button>
                  <button
                    v-if="!showCity && !city"
                    @click="showCity = true"
                    class="w-full text-left text-xs text-slate-400 hover:text-slate-600 transition-colors py-1"
                  >
                    + Base on a real city
                  </button>
                </div>

                <!-- CTA -->
                <button
                  @click="startSimulation"
                  :disabled="!rules.trim() || loading"
                  :class="[
                    'w-full py-3 rounded-xl font-semibold text-sm transition-all active:scale-[0.98]',
                    rules.trim() && !loading
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                      : 'bg-gray-100 text-slate-400 cursor-not-allowed'
                  ]"
                >
                  {{ loading ? 'Starting...' : 'Create your world' }}
                </button>

                <p class="text-center text-[10px] text-slate-400 leading-snug">
                  Estimated runtime: <span class="text-slate-500 font-medium">{{ estimatedTime }}</span>
                  <span class="text-slate-300 mx-0.5">&middot;</span>
                  {{ population * duration * 3 }} rounds
                </p>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import AgentSwarmCanvas from '../components/AgentSwarmCanvas.vue'

const router = useRouter()
const rules = ref('')
const proposedChange = ref('')
const showProposedChange = ref(false)
const segments = ref([])
const showSegments = ref(false)
const city = ref('')
const showCity = ref(false)
const population = ref(10)
const duration = ref(5)
const loading = ref(false)
const presets = ref([])

const populationOptions = [5, 10, 15, 20, 25, 50]
const durationOptions = [
  { value: 1, label: '1d' }, { value: 5, label: '5d' },
  { value: 10, label: '10d' }, { value: 30, label: '30d' },
  { value: 90, label: '90d' }, { value: 365, label: '1y' },
]

const visiblePresets = computed(() => presets.value.slice(0, 8))

const estimatedTime = computed(() => {
  const agents = population.value
  const days = duration.value
  const roundsPerDay = 3
  const totalRounds = days * roundsPerDay

  const activeMin = 3
  const activeMax = Math.max(3, Math.floor(agents * 0.4))
  const avgActive = Math.ceil((activeMin + activeMax) / 2)

  const concurrency = 10
  const avgLatency = 1.8

  const decisionBatches = Math.ceil(avgActive / concurrency)
  const decisionTime = decisionBatches * avgLatency

  const speechCount = Math.min(5, Math.ceil(avgActive * 0.4))
  const witnessesPerSpeech = Math.min(4, agents - 1)
  const silenceRate = 0.55
  const reactiveCallsSpeech = Math.ceil(speechCount * witnessesPerSpeech * (1 - silenceRate))
  const reactiveBatchesSpeech = Math.ceil(reactiveCallsSpeech / concurrency)

  const actionCount = Math.min(4, Math.ceil(avgActive * 0.25))
  const witnessesPerAction = Math.min(3, agents - 1)
  const reactiveCallsAction = Math.ceil(actionCount * witnessesPerAction * (1 - silenceRate))
  const reactiveBatchesAction = Math.ceil(reactiveCallsAction / concurrency)

  const reactionTime = (reactiveBatchesSpeech + reactiveBatchesAction) * avgLatency
  const narrationTime = avgLatency

  const perRound = decisionTime + reactionTime + narrationTime
  const totalSec = totalRounds * perRound

  const setupSec = avgLatency + (Math.ceil(agents / concurrency) * avgLatency) + 2

  const totalEstimate = setupSec + totalSec

  if (totalEstimate < 60) return `~${Math.round(totalEstimate)}s`
  if (totalEstimate < 3600) return `~${Math.round(totalEstimate / 60)} min`
  const hrs = Math.floor(totalEstimate / 3600)
  const mins = Math.round((totalEstimate % 3600) / 60)
  return `~${hrs}h ${mins}m`
})

function addSegment() { segments.value.push({ name: '', description: '' }) }
function removeSegment(i) { segments.value.splice(i, 1) }

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
  try {
    const data = await api.getPresets()
    presets.value = data.presets || []
  } catch (e) { console.error('Failed to load presets:', e) }
})

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
  city.value = ''
  showCity.value = false
}

async function startSimulation() {
  if (!rules.value.trim()) return
  loading.value = true
  try {
    const segs = segments.value.filter(s => (s.name || '').trim() || (s.description || '').trim())
    const data = await api.simulate(
      rules.value, population.value, duration.value,
      proposedChange.value.trim() || null,
      segs.length ? segs.map(s => ({ name: (s.name || '').trim(), description: (s.description || '').trim(), count: s.count || null })) : null,
      city.value.trim() || null
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
