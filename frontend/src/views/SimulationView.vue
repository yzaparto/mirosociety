<template>
  <div class="h-screen flex flex-col overflow-hidden bg-slate-950 text-slate-200">
    <!-- Toasts -->
    <ToastContainer :toasts="toasts" @dismiss="dismissToast" />

    <!-- Shortcuts overlay -->
    <ShortcutsOverlay v-model="showShortcuts" />

    <!-- Top bar - Row 1: Info -->
    <div class="h-11 border-b border-slate-800/60 flex items-center px-4 gap-3 shrink-0">
      <router-link to="/" class="text-slate-500 hover:text-slate-300 text-sm transition-colors">←</router-link>
      <h1 class="font-semibold text-sm truncate">{{ worldName || 'Generating...' }}</h1>
      <div v-if="currentDay" class="text-[11px] text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded font-mono">
        Day {{ currentDay }} · {{ currentTimeOfDay }}
      </div>
      <div v-if="phase === 'generating'" class="flex items-center gap-1.5">
        <div class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></div>
        <span class="text-[11px] text-emerald-400">Generating</span>
      </div>
      <div v-if="phase === 'running'" class="flex items-center gap-1.5">
        <div class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></div>
        <span class="text-[11px] text-emerald-400">Live</span>
      </div>
      <div v-if="phase === 'complete'" class="text-[11px] text-slate-500 bg-slate-800/40 px-2 py-0.5 rounded">Complete</div>
      <div class="flex-1"></div>
      <button @click="showShortcuts = true" class="text-slate-600 hover:text-slate-400 text-xs transition-colors" title="Keyboard shortcuts">?</button>
      <a
        href="https://github.com/yzaparto/mirosociety"
        target="_blank"
        rel="noopener noreferrer"
        class="flex items-center gap-1.5 text-slate-500 hover:text-white transition-colors"
        title="Star on GitHub"
      >
        <svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        <span class="text-[11px]">Star</span>
      </a>
    </div>

    <!-- Top bar - Row 2: Controls -->
    <div v-if="phase === 'running' || phase === 'complete'" class="h-10 border-b border-slate-800/40 flex items-center justify-center px-4 gap-2 shrink-0 bg-slate-900/20">
      <!-- View toggle with sliding indicator -->
      <div class="view-toggle relative flex bg-slate-800/50 rounded-lg p-0.5 border border-slate-700/40">
        <div class="view-toggle-indicator absolute top-0.5 bottom-0.5 rounded-md bg-emerald-600 shadow-sm shadow-emerald-900/40 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
          :style="{ left: viewMode === 'map' ? '2px' : '50%', width: 'calc(50% - 2px)' }"></div>
        <button @click="viewMode = 'map'"
          :class="['relative z-10 flex items-center gap-1.5 text-xs px-4 py-1.5 rounded-md transition-colors duration-200 font-medium', viewMode === 'map' ? 'text-white' : 'text-slate-400 hover:text-slate-200']">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 2a10 10 0 100 20 10 10 0 000-20z" opacity="0.3"/><path d="M19.07 4.93l-3.54 3.54M4.93 19.07l3.54-3.54M19.07 19.07l-3.54-3.54M4.93 4.93l3.54 3.54"/></svg>
          <span>Map</span>
          <span v-if="viewMode !== 'map'" class="text-[10px] text-slate-500 hidden sm:inline">Network</span>
        </button>
        <button @click="viewMode = 'feed'"
          :class="['relative z-10 flex items-center gap-1.5 text-xs px-4 py-1.5 rounded-md transition-colors duration-200 font-medium', viewMode === 'feed' ? 'text-white' : 'text-slate-400 hover:text-slate-200']">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M4 6h16M4 12h16M4 18h10"/></svg>
          <span>Feed</span>
          <span v-if="viewMode !== 'feed'" class="text-[10px] text-slate-500 hidden sm:inline">Events</span>
        </button>
      </div>

      <div class="w-px h-5 bg-slate-800/60"></div>

      <template v-if="phase === 'running'">
        <!-- Speed controls -->
        <div class="flex gap-0.5 bg-slate-800/40 rounded-lg p-0.5">
          <button v-for="s in speeds" :key="s.id" @click="doSetSpeed(s.id)"
            :class="['text-[11px] px-2.5 py-1 rounded-md transition-all duration-200 font-medium', speed === s.id ? s.active : 'text-slate-500 hover:text-slate-300']"
            :title="s.title">
            {{ s.label }}
          </button>
        </div>

        <div class="w-px h-5 bg-slate-800/60"></div>

        <button @click="togglePause"
          class="text-xs px-3 py-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors active:scale-[0.97]"
          title="Space">
          {{ paused ? 'Resume' : 'Pause' }}
        </button>
        <button @click="showInject = true"
          class="text-xs px-3 py-1.5 rounded-md hover:bg-amber-950/40 text-amber-500 hover:text-amber-400 transition-colors active:scale-[0.97]"
          title="I">
          Inject
        </button>
        <button @click="openFork()"
          class="text-xs px-3 py-1.5 rounded-md hover:bg-blue-950/40 text-blue-500 hover:text-blue-400 transition-colors active:scale-[0.97]"
          title="F">
          Fork
        </button>
        <button @click="stopSim"
          class="text-xs px-3 py-1.5 rounded-md hover:bg-red-950/40 text-red-500 hover:text-red-400 transition-colors active:scale-[0.97]">
          Stop
        </button>
      </template>
      <template v-if="phase === 'complete'">
        <button @click="openFork()" class="text-xs px-3 py-1.5 rounded-md hover:bg-blue-950/40 text-blue-500 hover:text-blue-400 transition-colors active:scale-[0.97]">Fork</button>
        <router-link :to="`/report/${simId}`" class="text-xs px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white transition-colors active:scale-[0.97]">View Report →</router-link>
      </template>
    </div>

    <!-- ===== GENERATION PHASE ===== -->
    <div v-if="phase === 'generating'" class="flex-1 flex items-center justify-center">
      <div class="max-w-lg w-full px-6 space-y-6">
        <!-- Cancel button -->
        <div class="flex justify-end">
          <button
            @click="cancelSim"
            :disabled="cancelling"
            class="text-xs px-3 py-1.5 rounded-md hover:bg-red-950/40 text-red-500 hover:text-red-400 transition-colors active:scale-[0.97] disabled:opacity-50"
          >
            {{ cancelling ? 'Cancelling...' : 'Cancel' }}
          </button>
        </div>

        <!-- Progress stepper -->
        <div class="space-y-3">
          <div v-for="(step, i) in genSteps" :key="step.id"
            :class="['flex items-center gap-3 transition-all duration-500', { 'opacity-40': step.status === 'pending' }]"
            :style="{ transitionDelay: (i * 50) + 'ms' }">
            <div v-if="step.status === 'done'" class="w-5 h-5 rounded-full bg-emerald-600 flex items-center justify-center shrink-0">
              <svg class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </div>
            <div v-else-if="step.status === 'active'" class="w-5 h-5 rounded-full border-2 border-emerald-400 flex items-center justify-center shrink-0">
              <div class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
            </div>
            <div v-else class="w-5 h-5 rounded-full border border-slate-700 shrink-0"></div>
            <span :class="['text-sm', step.status === 'active' ? 'text-emerald-400' : step.status === 'done' ? 'text-slate-300' : 'text-slate-600']">
              {{ step.label }}
            </span>
          </div>
        </div>

        <!-- World info (revealed when ready) -->
        <Transition name="feed">
          <div v-if="worldName" class="space-y-2">
            <h2 class="text-2xl font-bold">{{ worldName }}</h2>
            <p class="text-slate-400 text-sm leading-relaxed">{{ worldDescription }}</p>
            <div v-if="locations.length" class="flex flex-wrap gap-1.5 mt-3">
              <TransitionGroup name="list">
                <span v-for="loc in locations" :key="loc.id"
                  class="text-[11px] px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-400">
                  {{ locIcon(loc.type) }} {{ loc.name }}
                </span>
              </TransitionGroup>
            </div>
          </div>
        </Transition>

        <!-- Citizens (staggered reveal) -->
        <div v-if="citizens.length" class="space-y-3">
          <p class="text-[11px] text-slate-500 uppercase tracking-wider">Citizens ({{ citizens.length }} generated)</p>
          <div class="grid grid-cols-2 gap-1.5">
            <TransitionGroup name="list">
              <div v-for="c in citizens" :key="c.id"
                class="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-slate-900/60 border border-slate-800/60">
                <MoodDot :state="c.emotional_state" />
                <div class="min-w-0">
                  <div class="text-sm font-medium truncate">{{ c.name }}</div>
                  <div class="text-[11px] text-slate-500">{{ c.role }}</div>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== SIMULATION PHASE ===== -->
    <div v-if="phase === 'running' || phase === 'complete'" class="flex-1 flex overflow-hidden">

      <!-- ========== MAP VIEW ========== -->
      <template v-if="viewMode === 'map'">
        <div class="flex-1 flex flex-col overflow-hidden">
          <div class="flex-1 relative overflow-hidden" ref="graphContainer">
            <svg ref="graphSvg" class="w-full h-full"></svg>

            <!-- Speech bubbles -->
            <div v-for="(text, agentId) in speechBubbles" :key="agentId"
              class="fixed z-[60] speech-bubble-anim pointer-events-none"
              :style="getNodeBubbleStyle(agentId)">
              <div :class="['text-[10px] px-2.5 py-1.5 rounded-xl shadow-xl max-w-[220px] leading-snug',
                speechBubbleClass(agentMap[agentId]?.emotional_state)]">
                "{{ text }}"
              </div>
            </div>

            <!-- Hover tooltip -->
            <Transition name="feed">
              <div v-if="hoveredAgentId && agentMap[hoveredAgentId]"
                class="fixed z-[55] pointer-events-none"
                :style="getNodeTooltipStyle(hoveredAgentId)">
                <div class="bg-slate-800 border border-slate-700 rounded-lg shadow-xl px-3 py-2.5 min-w-[180px] max-w-[260px]">
                  <div class="flex items-center gap-1.5 mb-1">
                    <MoodDot :state="agentMap[hoveredAgentId].emotional_state" />
                    <span class="text-[11px] font-semibold">{{ agentMap[hoveredAgentId].name }}</span>
                    <span class="text-[9px] text-slate-500">{{ agentMap[hoveredAgentId].role }}</span>
                  </div>
                  <div class="text-[10px] text-slate-400 italic">{{ agentMap[hoveredAgentId].emotional_state }}</div>
                  <div v-if="agentMap[hoveredAgentId].faction" class="text-[9px] text-violet-300 mt-0.5">{{ agentMap[hoveredAgentId].faction }}</div>
                  <div v-if="agentLastAction[hoveredAgentId]" class="text-[10px] text-slate-300 mt-1.5 border-t border-slate-700 pt-1.5">
                    {{ agentLastAction[hoveredAgentId] }}
                  </div>
                </div>
              </div>
            </Transition>

            <!-- Zoom controls -->
            <div class="absolute bottom-3 right-3 flex flex-col gap-1 z-20">
              <button @click="zoomIn" class="w-7 h-7 rounded-md bg-slate-800 border border-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors text-sm flex items-center justify-center" title="Zoom in">+</button>
              <button @click="zoomOut" class="w-7 h-7 rounded-md bg-slate-800 border border-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors text-sm flex items-center justify-center" title="Zoom out">−</button>
              <button @click="zoomReset" class="w-7 h-7 rounded-md bg-slate-800 border border-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors text-[9px] flex items-center justify-center" title="Reset zoom">R</button>
            </div>

            <!-- Legend -->
            <div class="absolute bottom-3 left-3 z-20">
              <button @click="showLegend = !showLegend"
                class="text-[9px] text-slate-500 hover:text-slate-300 bg-slate-800 border border-slate-700/60 rounded-md px-2 py-1 transition-colors">
                {{ showLegend ? '▼ Legend' : '▶ Legend' }}
              </button>
              <Transition name="feed">
                <div v-if="showLegend" class="mt-1 bg-slate-800 border border-slate-700/60 rounded-lg p-2.5 space-y-1.5">
                  <div v-for="item in legendItems" :key="item.label" class="flex items-center gap-2">
                    <div :class="['w-2.5 h-2.5 rounded-full', item.color]"></div>
                    <span class="text-[9px] text-slate-400">{{ item.label }}</span>
                  </div>
                </div>
              </Transition>
            </div>
          </div>

          <!-- Metrics bar at bottom -->
          <MetricsStrip :metrics="metrics" :prev-metrics="prevMetrics" :show-market="isMarketSim">
            <template #right>
              <div v-if="institutions.length" class="flex gap-2">
                <span v-for="inst in institutions" :key="inst.name" class="text-[9px] text-violet-300 bg-violet-950/40 px-1.5 py-0.5 rounded">
                  {{ inst.name }}
                </span>
              </div>
            </template>
          </MetricsStrip>
        </div>
      </template>

      <!-- ========== FEED VIEW ========== -->
      <template v-if="viewMode === 'feed'">
        <!-- LEFT sidebar - Agent list -->
        <div class="w-60 shrink-0 border-r border-slate-800/60 flex flex-col overflow-hidden">
          <!-- Compact metrics -->
          <div class="px-3 py-2 border-b border-slate-800/40">
            <div class="grid grid-cols-5 gap-1">
              <div v-for="m in SOCIAL_METRICS" :key="m.key" class="text-center">
                <div class="text-[8px] text-slate-500 leading-none mb-0.5 flex items-center justify-center gap-0.5">
                  {{ m.label.slice(0, 5) }}
                </div>
                <div class="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div :class="['h-full rounded-full transition-all duration-700', metricBarColorFn(m.key)]"
                    :style="{ width: ((metrics[m.key] ?? 0) * 100) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Search -->
          <div class="px-2 py-1.5 border-b border-slate-800/30">
            <input
              v-model="agentSearch"
              placeholder="Search citizens..."
              class="w-full bg-slate-900/60 border border-slate-800/40 rounded-md px-2 py-1 text-[10px] outline-none focus:border-emerald-600/50 placeholder-slate-600 transition-colors"
            />
          </div>

          <!-- Agent list -->
          <div class="flex-1 overflow-y-auto px-1.5 py-1">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider px-2 py-1">Citizens ({{ filteredAgents.length }})</div>
            <div
              v-for="a in filteredAgents"
              :key="a.id"
              @click="selectAgent(a.id)"
              :class="[
                'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors mb-0.5',
                selectedAgentId === a.id ? 'bg-slate-800 border border-emerald-800/30' : 'hover:bg-slate-800/50'
              ]"
            >
              <AgentAvatar :agent="a" :selected="selectedAgentId === a.id" size="sm" @click.stop="selectAgent(a.id)" />
              <div class="min-w-0 flex-1">
                <div class="text-[11px] font-medium truncate">{{ a.name }}</div>
                <div class="text-[9px] text-slate-500 truncate italic">{{ a.emotional_state || a.role }}</div>
              </div>
              <div v-if="a.faction" class="text-[8px] text-violet-400 bg-violet-900/30 px-1 py-0.5 rounded shrink-0">{{ a.faction }}</div>
            </div>
          </div>
        </div>

        <!-- CENTER: Event feed -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <div class="flex-1 overflow-y-auto" ref="feedRef" @scroll="onFeedScroll">
            <div class="max-w-4xl mx-auto px-6 py-4">
              <!-- Empty state -->
              <div v-if="!rawEvents.length" class="flex flex-col items-center justify-center py-20 text-slate-600">
                <div class="w-8 h-8 border-2 border-slate-700 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                <p class="text-sm">Waiting for the first day to begin...</p>
              </div>

              <template v-for="(group, gi) in groupedEvents" :key="gi">
                <div class="sticky top-0 z-10 py-2">
                  <div class="text-xs text-slate-500 font-semibold uppercase tracking-wider bg-slate-950/90 backdrop-blur-sm py-1.5 px-3 rounded-md inline-block">
                    Day {{ group.day }} · {{ group.tod }}
                  </div>
                </div>
                <div class="mb-5 space-y-0.5">
                  <div v-for="(evt, ei) in group.events" :key="ei"
                    :class="[
                      'py-2.5 px-4 rounded-md text-sm leading-relaxed transition-colors',
                      evt.highlight ? 'bg-amber-950/10 border-l-2 border-amber-600/40' : 'border-l-2 border-transparent hover:bg-slate-900/40'
                    ]">
                    <span v-html="evt.html"></span>
                  </div>
                </div>
              </template>

              <div v-if="phase === 'complete' && rawEvents.length" class="text-center py-8 border-t border-slate-800/40 mt-4">
                <p class="text-slate-500 text-sm mb-3">The simulation has ended.</p>
                <router-link :to="`/report/${simId}`" class="btn-primary text-sm px-5 py-2.5">View Full Report →</router-link>
              </div>
            </div>
          </div>

          <!-- Scroll to bottom FAB -->
          <Transition name="feed">
            <button
              v-if="userScrolledUp && rawEvents.length"
              @click="scrollToBottom"
              class="absolute bottom-14 right-8 z-20 w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center shadow-lg hover:bg-emerald-500 transition-colors text-sm active:scale-[0.95]"
            >
              ↓
            </button>
          </Transition>
        </div>
      </template>

      <!-- RIGHT: Agent detail panel -->
      <AgentDetailPanel
        :agent="selectedAgent"
        :chat-messages="chatMessages"
        :chat-loading="chatLoading"
        @close="selectedAgentId = null"
        @chat="sendChat"
      />
    </div>

    <!-- Inject modal -->
    <InjectModal v-model="showInject" @inject="doInject" />

    <!-- Fork modal -->
    <ForkModal
      v-model="showFork"
      :max-day="currentDay || 1"
      :initial-day="currentDay || 1"
      :forking="forking"
      @fork="doFork"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as d3 from 'd3'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'

import { moodDotClass, moodNodeFill, moodNodeStroke, speechBubbleClass } from '../utils/mood'
import { SOCIAL_METRICS, MARKET_METRICS, MARKET_METRIC_KEYS, metricBarColor as metricBarColorFn } from '../utils/metrics'
import { escapeHtml, nameSpan, locIcon } from '../utils/format'

import MoodDot from '../components/MoodDot.vue'
import AgentAvatar from '../components/AgentAvatar.vue'
import AgentDetailPanel from '../components/AgentDetailPanel.vue'
import MetricsStrip from '../components/MetricsStrip.vue'
import ToastContainer from '../components/ToastContainer.vue'
import InjectModal from '../components/InjectModal.vue'
import ForkModal from '../components/ForkModal.vue'
import ShortcutsOverlay from '../components/ShortcutsOverlay.vue'

const route = useRoute()
const router = useRouter()
const simId = route.params.id

// ---- STATE ----
const phase = ref('generating')
const viewMode = ref('map')
const statusText = ref('Connecting...')
const worldName = ref('')
const worldDescription = ref('')
const locations = ref([])
const citizens = ref([])
const agentMap = reactive({})
const metrics = ref({ stability: 0.5, prosperity: 0.5, trust: 0.5, freedom: 0.5, conflict: 0.2 })
const prevMetrics = ref({ stability: 0.5, prosperity: 0.5, trust: 0.5, freedom: 0.5, conflict: 0.2 })
const currentDay = ref(0)
const currentTimeOfDay = ref('morning')
const paused = ref(false)
const speed = ref('live')
const selectedAgentId = ref(null)
const hoveredAgentId = ref(null)
const showInject = ref(false)
const showFork = ref(false)
const forking = ref(false)
const showShortcuts = ref(false)
const showLegend = ref(false)
const cancelling = ref(false)
const agentSearch = ref('')
const chatMessages = ref([])
const chatLoading = ref(false)
const institutions = ref([])
const feedRef = ref(null)
const rawEvents = ref([])
const toasts = ref([])
const actorFlash = reactive({})
const speechBubbles = reactive({})
const agentLastAction = reactive({})

let toastCounter = 0

// Generation stepper
const genSteps = ref([
  { id: 'world', label: 'Creating world...', status: 'active' },
  { id: 'locations', label: 'Generating locations...', status: 'pending' },
  { id: 'citizens', label: 'Generating citizens...', status: 'pending' },
  { id: 'start', label: 'Starting simulation...', status: 'pending' },
])

function advanceGenStep(id) {
  let found = false
  for (const step of genSteps.value) {
    if (step.id === id) {
      step.status = 'done'
      found = true
    } else if (found && step.status === 'pending') {
      step.status = 'active'
      break
    }
  }
}

// D3 graph refs
const graphContainer = ref(null)
const graphSvg = ref(null)
const nodePositions = reactive({})
const graphEdges = ref([])
let simulation = null
let svgSelection = null
let gSelection = null
let linkGroup = null
let nodeGroup = null
let zoomBehavior = null
let edgeCounter = 0
let currentTransform = d3.zoomIdentity
let eventSource = null

const speeds = [
  { id: 'live', label: '1×', active: 'bg-emerald-600 text-white', title: 'Normal speed (1)' },
  { id: 'fast_forward', label: '5×', active: 'bg-amber-600 text-white', title: 'Fast forward (2)' },
  { id: 'jump', label: '10×', active: 'bg-violet-600 text-white', title: 'Jump ahead (3)' },
]

const legendItems = [
  { color: 'bg-emerald-400', label: 'Calm / Content / Hopeful' },
  { color: 'bg-amber-400', label: 'Restless / Uneasy / Anxious' },
  { color: 'bg-red-400', label: 'Angry / Hostile / Fearful' },
  { color: 'bg-violet-400', label: 'Conflicted / Torn / Confused' },
  { color: 'bg-slate-400', label: 'Neutral' },
]

// ---- COMPUTED ----
const isMarketSim = computed(() => {
  const m = metrics.value
  return m && (
    (m.word_of_mouth || 0) > 0 ||
    (m.adoption_rate || 0) > 0 ||
    (m.churn_risk ?? 0.2) !== 0.2 ||
    (m.brand_sentiment ?? 0.5) !== 0.5 ||
    (m.purchase_intent ?? 0.5) !== 0.5
  )
})

const allAgents = computed(() => Object.values(agentMap))

const filteredAgents = computed(() => {
  const q = agentSearch.value.toLowerCase().trim()
  if (!q) return allAgents.value
  return allAgents.value.filter(a =>
    a.name?.toLowerCase().includes(q) ||
    a.role?.toLowerCase().includes(q) ||
    a.faction?.toLowerCase().includes(q)
  )
})

const selectedAgent = computed(() => {
  if (selectedAgentId.value === null) return null
  return agentMap[selectedAgentId.value] || citizens.value.find(c => c.id === selectedAgentId.value) || null
})

const groupedEvents = computed(() => {
  const groups = []
  let current = null
  for (const evt of rawEvents.value) {
    const key = `${evt.day}-${evt.tod}`
    if (!current || current.key !== key) {
      current = { key, day: evt.day, tod: evt.tod, events: [] }
      groups.push(current)
    }
    current.events.push(evt)
  }
  return groups
})

function selectAgent(id) {
  selectedAgentId.value = selectedAgentId.value === id ? null : id
  chatMessages.value = []
}

// ---- D3 FORCE GRAPH ----
function getScreenPos(agentId) {
  const pos = nodePositions[agentId]
  if (!pos || !graphContainer.value) return null
  const rect = graphContainer.value.getBoundingClientRect()
  return {
    x: rect.left + currentTransform.applyX(pos.x),
    y: rect.top + currentTransform.applyY(pos.y),
  }
}

function getNodeBubbleStyle(agentId) {
  const sp = getScreenPos(agentId)
  if (!sp) return { display: 'none' }
  const bubbleW = 230
  const bubbleH = 50
  return {
    left: Math.max(8, Math.min(sp.x - bubbleW / 2, window.innerWidth - bubbleW - 8)) + 'px',
    top: Math.max(8, sp.y - bubbleH - 28) + 'px',
  }
}

function getNodeTooltipStyle(agentId) {
  const sp = getScreenPos(agentId)
  if (!sp) return { display: 'none' }
  const tooltipW = 260
  const tooltipH = 80
  return {
    left: Math.max(8, Math.min(sp.x - tooltipW / 2, window.innerWidth - tooltipW - 8)) + 'px',
    top: Math.max(8, sp.y - tooltipH - 28) + 'px',
  }
}

function initGraph() {
  if (!graphContainer.value || !graphSvg.value) return
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  svgSelection = d3.select(graphSvg.value).attr('width', width).attr('height', height)
  svgSelection.selectAll('*').remove()

  const defs = svgSelection.append('defs')
  const pattern = defs.append('pattern').attr('id', 'dot-grid').attr('width', 24).attr('height', 24).attr('patternUnits', 'userSpaceOnUse')
  pattern.append('circle').attr('cx', 12).attr('cy', 12).attr('r', 1).attr('fill', '#1e293b')

  svgSelection.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#dot-grid)')
  gSelection = svgSelection.append('g')
  linkGroup = gSelection.append('g').attr('class', 'edges')
  nodeGroup = gSelection.append('g').attr('class', 'nodes')

  zoomBehavior = d3.zoom()
    .scaleExtent([0.2, 4])
    .on('zoom', (event) => {
      currentTransform = event.transform
      gSelection.attr('transform', event.transform)
    })
  svgSelection.call(zoomBehavior)
  svgSelection.on('click', () => {
    selectedAgentId.value = null
    hoveredAgentId.value = null
  })

  const agents = Object.values(agentMap)
  const nodes = agents.map(a => ({
    id: a.id,
    x: nodePositions[a.id]?.x ?? width / 2 + (Math.random() - 0.5) * 200,
    y: nodePositions[a.id]?.y ?? height / 2 + (Math.random() - 0.5) * 200,
  }))

  simulation = d3.forceSimulation(nodes)
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('charge', d3.forceManyBody().strength(-280))
    .force('collide', d3.forceCollide().radius(45))
    .force('x', d3.forceX(width / 2).strength(0.05))
    .force('y', d3.forceY(height / 2).strength(0.05))
    .on('tick', onSimTick)

  renderNodes()
}

function onSimTick() {
  if (!simulation) return
  for (const n of simulation.nodes()) {
    nodePositions[n.id] = { x: n.x, y: n.y }
  }
  updateNodePositions()
  updateEdgePositions()
}

function renderNodes() {
  if (!nodeGroup || !simulation) return
  nodeGroup.selectAll('*').remove()
  const agents = Object.values(agentMap)
  const nodes = simulation.nodes()
  const nodeMap = {}
  nodes.forEach(n => { nodeMap[n.id] = n })

  const nodeG = nodeGroup.selectAll('g.agent-node')
    .data(agents, d => d.id)
    .enter().append('g').attr('class', 'agent-node')
    .attr('transform', d => { const pos = nodeMap[d.id]; return pos ? `translate(${pos.x}, ${pos.y})` : 'translate(0,0)' })
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => { const n = nodeMap[d.id]; if (!n) return; if (!event.active) simulation.alphaTarget(0.3).restart(); n.fx = n.x; n.fy = n.y })
      .on('drag', (event, d) => { const n = nodeMap[d.id]; if (n) { n.fx = event.x; n.fy = event.y } })
      .on('end', (event, d) => { const n = nodeMap[d.id]; if (!n) return; if (!event.active) simulation.alphaTarget(0); n.fx = null; n.fy = null })
    )
    .on('click', (event, d) => { event.stopPropagation(); selectAgent(d.id) })
    .on('mouseenter', (event, d) => { hoveredAgentId.value = d.id })
    .on('mouseleave', () => { hoveredAgentId.value = null })

  nodeG.append('circle').attr('class', 'select-ring').attr('r', 28).attr('fill', 'none').attr('stroke', 'transparent').attr('stroke-width', 2.5)
  nodeG.append('circle').attr('class', 'node-circle').attr('r', 22)
    .attr('fill', d => moodNodeFill(d.emotional_state))
    .attr('stroke', d => moodNodeStroke(d.emotional_state))
    .attr('stroke-width', 2.5).attr('opacity', 0.9)
  nodeG.append('text').attr('class', 'node-initial').attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
    .attr('fill', '#fff').attr('font-size', '13px').attr('font-weight', '700').attr('pointer-events', 'none')
    .text(d => d.name.charAt(0))
  nodeG.append('text').attr('class', 'node-label').attr('text-anchor', 'middle').attr('y', 34)
    .attr('fill', '#94a3b8').attr('font-size', '10px').attr('font-weight', '500').attr('pointer-events', 'none')
    .text(d => d.name.split(' ')[0])
}

function updateNodePositions() {
  if (!nodeGroup || !simulation) return
  const nodeMap = {}
  simulation.nodes().forEach(n => { nodeMap[n.id] = n })
  nodeGroup.selectAll('g.agent-node').attr('transform', d => {
    const pos = nodeMap[d.id]
    return pos ? `translate(${pos.x}, ${pos.y})` : null
  })
}

function updateNodeAppearance() {
  if (!nodeGroup) return
  const agentLookup = {}
  Object.values(agentMap).forEach(a => { agentLookup[a.id] = a })

  nodeGroup.selectAll('g.agent-node').each(function (d) {
    const agent = agentLookup[d.id]
    if (!agent) return
    const g = d3.select(this)
    g.select('.node-circle').transition().duration(600)
      .attr('fill', moodNodeFill(agent.emotional_state))
      .attr('stroke', moodNodeStroke(agent.emotional_state))
    g.select('.select-ring')
      .attr('stroke', selectedAgentId.value === d.id ? '#fff' : 'transparent')
      .attr('stroke-opacity', selectedAgentId.value === d.id ? 0.6 : 0)
  })
}

function flashNode(agentId) {
  if (!nodeGroup) return
  nodeGroup.selectAll('g.agent-node').filter(d => d.id === agentId)
    .select('.select-ring').attr('stroke', '#facc15').attr('stroke-opacity', 0.8)
    .transition().duration(1500).attr('stroke-opacity', 0).attr('stroke', 'transparent')
}

function addGraphEdge(agentId1, agentId2, color = '#6ee7b7') {
  if (!agentId1 || !agentId2 || agentId1 === agentId2) return
  if (!nodePositions[agentId1] || !nodePositions[agentId2]) return
  const id = ++edgeCounter
  graphEdges.value.push({ id, source: agentId1, target: agentId2, color, timestamp: Date.now() })
  renderEdges()
  setTimeout(() => { graphEdges.value = graphEdges.value.filter(e => e.id !== id); renderEdges() }, 10000)
}

function renderEdges() {
  if (!linkGroup) return
  const paths = linkGroup.selectAll('path.interaction-edge').data(graphEdges.value, d => d.id)
  paths.exit().remove()
  paths.enter().append('path').attr('class', 'interaction-edge')
    .attr('fill', 'none').attr('stroke', d => d.color).attr('stroke-width', 2.2)
    .attr('stroke-opacity', 0.5).attr('stroke-linecap', 'round').attr('d', d => computeEdgePath(d))
    .attr('stroke-dasharray', function() { return this.getTotalLength() })
    .attr('stroke-dashoffset', function() { return this.getTotalLength() })
    .transition().duration(400).attr('stroke-dashoffset', 0)
  paths.attr('stroke', d => d.color).attr('d', d => computeEdgePath(d))
}

function computeEdgePath(edge) {
  const p1 = nodePositions[edge.source]
  const p2 = nodePositions[edge.target]
  if (!p1 || !p2) return ''
  const dx = p2.x - p1.x, dy = p2.y - p1.y
  const dist = Math.sqrt(dx * dx + dy * dy)
  const offset = Math.max(20, dist * 0.15)
  const mx = (p1.x + p2.x) / 2 + (-dy / (dist || 1)) * offset
  const my = (p1.y + p2.y) / 2 + (dx / (dist || 1)) * offset
  return `M${p1.x},${p1.y} Q${mx},${my} ${p2.x},${p2.y}`
}

function updateEdgePositions() {
  if (!linkGroup) return
  linkGroup.selectAll('path.interaction-edge').attr('d', d => computeEdgePath(d))
}

function addSimulationNode(agentId) {
  if (!simulation || !graphContainer.value) return
  const container = graphContainer.value
  const nodes = simulation.nodes()
  if (nodes.find(n => n.id === agentId)) return
  nodes.push({ id: agentId, x: container.clientWidth / 2 + (Math.random() - 0.5) * 200, y: container.clientHeight / 2 + (Math.random() - 0.5) * 200 })
  simulation.nodes(nodes)
  simulation.alpha(0.3).restart()
  renderNodes()
}

// Zoom controls
function zoomIn() { if (svgSelection && zoomBehavior) svgSelection.transition().duration(300).call(zoomBehavior.scaleBy, 1.3) }
function zoomOut() { if (svgSelection && zoomBehavior) svgSelection.transition().duration(300).call(zoomBehavior.scaleBy, 0.7) }
function zoomReset() { if (svgSelection && zoomBehavior) svgSelection.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity) }

// ---- TOAST HELPERS ----
function addToast(text, type = 'info') {
  const id = ++toastCounter
  toasts.value.push({ id, text, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 5000)
}

function dismissToast(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

function addEvent(html, opts = {}) {
  rawEvents.value.push({ day: currentDay.value, tod: currentTimeOfDay.value || 'morning', html, highlight: opts.highlight || false, location: opts.location || null })
  if (rawEvents.value.length > 800) rawEvents.value.splice(0, 200)
}

function flashActor(id) {
  actorFlash[id] = true
  flashNode(id)
  setTimeout(() => { delete actorFlash[id] }, 2500)
}

function showSpeech(agentId, text) {
  if (!text) return
  speechBubbles[agentId] = text.length > 120 ? text.slice(0, 120) + '...' : text
  setTimeout(() => { delete speechBubbles[agentId] }, 6000)
}

function agentNameById(id) { return agentMap[id]?.name || `Citizen ${id}` }
function locName(locId) { return locations.value.find(l => l.id === locId)?.name || locId }

// ---- STAGGERED ACTION QUEUE ----
const actionQueue = []
let drainRunning = false

function getStaggerDelay() {
  if (speed.value === 'jump') return 50
  if (speed.value === 'fast_forward') return 120
  return 400
}

async function drainActionQueue() {
  if (drainRunning) return
  drainRunning = true
  while (actionQueue.length > 0) {
    const fn = actionQueue.shift()
    fn()
    await new Promise(r => setTimeout(r, getStaggerDelay()))
  }
  drainRunning = false
}

function enqueue(fn) {
  actionQueue.push(fn)
  if (!drainRunning) drainActionQueue()
}

// ---- PROCESS ROUND ----
function processRound(actions, reactions, tensionEvent, narrative) {
  const visibleActions = actions.filter(a => a.action_type !== 'COMPLY' && a.action_type !== 'DO_NOTHING')
  const silentActions = actions.filter(a => a.action_type === 'COMPLY' || a.action_type === 'DO_NOTHING')

  for (const a of silentActions) {
    agentLastAction[a.agent_id] = a.action_type === 'COMPLY' ? 'Going about their day' : 'Idle'
  }

  if (narrative) {
    enqueue(() => { addEvent(`<div class="text-slate-300 text-[12px] leading-relaxed italic border-l-2 border-slate-600/40 pl-3 my-1">${escapeHtml(narrative)}</div>`) })
  }

  for (const a of visibleActions) { enqueue(() => processOneAction(a)) }
  if (reactions) { for (const r of reactions) { enqueue(() => processOneReaction(r)) } }

  if (tensionEvent) {
    enqueue(() => {
      addEvent(`<span class="text-amber-300 font-medium">${tensionEvent}</span>`, { highlight: true })
      addToast(tensionEvent, 'warning')
    })
  }
}

function processOneAction(a) {
  flashActor(a.agent_id)
  const who = nameSpan(a.agent_name)
  const loc = a.location
  const at = a.action_type
  const agentIdNum = Number(a.agent_id)

  if (at === 'SPEAK_PUBLIC' && a.speech) {
    addEvent(`${who}: <span class="text-slate-200">"${escapeHtml(a.speech)}"</span>`, { location: loc })
    showSpeech(a.agent_id, a.speech)
    agentLastAction[a.agent_id] = `Said: "${a.speech.length > 50 ? a.speech.slice(0, 50) + '...' : a.speech}"`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    for (const hId of others.sort(() => Math.random() - 0.5).slice(0, Math.min(3, others.length))) {
      addGraphEdge(agentIdNum, hId, '#fbbf24')
    }
  } else if (at === 'SPEAK_PRIVATE' && a.speech) {
    const targetId = a.targets?.[0]
    const target = targetId != null ? nameSpan(agentNameById(targetId)) : 'someone'
    addEvent(`${who} whispered to ${target}: <span class="text-slate-400 italic">"${escapeHtml(a.speech)}"</span>`, { location: loc })
    showSpeech(a.agent_id, a.speech)
    if (targetId != null) addGraphEdge(agentIdNum, Number(targetId), '#fbbf24')
    agentLastAction[a.agent_id] = `Whispered to ${targetId != null ? agentNameById(targetId) : 'someone'}`
  } else if (at === 'TRADE') {
    const args = a.action_args || {}
    const targetId = args.target_id
    const target = targetId != null ? nameSpan(agentNameById(targetId)) : 'someone'
    const detail = args.give_resource ? ` — ${args.give_amount || '?'} ${escapeHtml(args.give_resource)} for ${args.receive_amount || '?'} ${escapeHtml(args.receive_resource || '?')}` : ''
    addEvent(`${who} traded with ${target}${detail}`, { location: loc })
    if (targetId != null) addGraphEdge(agentIdNum, Number(targetId), '#6ee7b7')
    agentLastAction[a.agent_id] = `Traded with ${targetId != null ? agentNameById(targetId) : 'someone'}`
  } else if (at === 'FORM_GROUP') {
    const gName = escapeHtml(a.action_args?.name || 'a group')
    addEvent(`${who} founded <span class="text-violet-300 font-medium">${gName}</span>`, { highlight: true, location: loc })
    addToast(`${a.agent_name} founded "${a.action_args?.name || 'a group'}"`, 'institution')
    agentLastAction[a.agent_id] = `Founded ${a.action_args?.name || 'a group'}`
  } else if (at === 'PROPOSE_RULE') {
    const content = a.action_args?.content || a.speech || 'a new rule'
    addEvent(`${who} proposed a rule: <span class="text-amber-200">"${escapeHtml(content)}"</span>`, { highlight: true, location: loc })
    agentLastAction[a.agent_id] = `Proposed: "${content.slice(0, 40)}..."`
  } else if (at === 'VOTE') {
    const vote = a.action_args?.vote === 'against' ? 'against' : 'for'
    addEvent(`${who} voted <span class="${vote === 'for' ? 'text-emerald-300' : 'text-red-300'} font-medium">${vote}</span>`, { location: loc })
    agentLastAction[a.agent_id] = `Voted ${vote}`
  } else if (at === 'PROTEST') {
    const target = escapeHtml(a.action_args?.target || 'the current order')
    addEvent(`${who} protested <span class="text-red-300">${target}</span>`, { highlight: true, location: loc })
    addToast(`${a.agent_name} is protesting!`, 'warning')
    agentLastAction[a.agent_id] = `Protesting: ${(a.action_args?.target || 'the current order').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'DEFECT') {
    const how = escapeHtml(a.action_args?.how || 'broke the rules')
    addEvent(`${who} <span class="text-red-400 font-medium">defected</span> — ${how}`, { highlight: true, location: loc })
    addToast(`${a.agent_name} defected!`, 'danger')
    agentLastAction[a.agent_id] = `DEFECTED: ${(a.action_args?.how || 'broke the rules').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'BUILD') {
    const what = escapeHtml(a.action_args?.what || 'something')
    addEvent(`${who} built <span class="text-blue-300">${what}</span>`, { location: loc })
    agentLastAction[a.agent_id] = `Built ${a.action_args?.what || 'something'}`
  } else if (at === 'RECOMMEND') {
    const targetId = a.action_args?.target_id || a.targets?.[0]
    const target = targetId != null ? nameSpan(agentNameById(targetId)) : 'someone'
    addEvent(`${who} recommended to ${target}`, { location: loc })
    if (targetId != null) addGraphEdge(agentIdNum, Number(targetId), '#6ee7b7')
    agentLastAction[a.agent_id] = `Recommended to ${targetId != null ? agentNameById(targetId) : 'someone'}`
  } else if (at === 'ABANDON') {
    const what = escapeHtml(a.action_args?.what || 'their position')
    addEvent(`${who} <span class="text-red-300">abandoned</span> ${what}`, { highlight: true, location: loc })
    agentLastAction[a.agent_id] = `Abandoned: ${(a.action_args?.what || 'their position').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'COMPARE') {
    addEvent(`<span class="text-slate-500">${escapeHtml(a.agent_name)} compared options</span>`, { location: loc })
    agentLastAction[a.agent_id] = 'Comparing...'
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#94a3b8')
  } else if (at === 'OBSERVE') {
    addEvent(`<span class="text-slate-500">${escapeHtml(a.agent_name)} observed the scene</span>`, { location: loc })
    agentLastAction[a.agent_id] = 'Observing...'
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#94a3b8')
  } else {
    addEvent(`${who}: ${escapeHtml(at)}`, { location: loc })
  }

  if (a.world_state_changes?.rule_passed) {
    addEvent(`<span class="text-emerald-300 font-medium">New community rule: "${escapeHtml(a.world_state_changes.rule_passed)}"</span>`, { highlight: true })
    addToast('New rule passed!', 'info')
  }
  if (a.world_state_changes?.rule_rejected) {
    addEvent(`<span class="text-red-300">Rule rejected: "${escapeHtml(a.world_state_changes.rule_rejected)}"</span>`)
  }
  if (a.world_state_changes?.institution_created) {
    addEvent(`<span class="text-violet-300 font-medium">New institution formed: ${escapeHtml(a.world_state_changes.institution_created)}</span>`, { highlight: true })
  }
}

function processOneReaction(r) {
  const loc = r.location || null
  if (r.reaction_type === 'respond' && r.content) {
    flashActor(r.agent_id)
    addEvent(`${nameSpan(r.agent_name)}: <span class="text-sky-200">"${escapeHtml(r.content)}"</span>`, { location: loc })
    showSpeech(r.agent_id, r.content)
    agentLastAction[r.agent_id] = `Responded: "${r.content.slice(0, 40)}..."`
  } else if (r.reaction_type === 'whisper' && r.content) {
    addEvent(`<span class="text-slate-400">${escapeHtml(r.agent_name)} whispered back: <span class="italic">"${escapeHtml(r.content)}"</span></span>`, { location: loc })
    agentLastAction[r.agent_id] = 'Whispered a response'
  }
}

// ---- ACTIONS ----
async function togglePause() {
  if (phase.value !== 'running') return
  try {
    if (paused.value) { await api.resume(simId); paused.value = false; addToast('Simulation resumed', 'info') }
    else { await api.pause(simId); paused.value = true; addToast('Simulation paused', 'info') }
  } catch (err) {
    addToast('Failed to pause/resume: ' + (err.response?.data?.detail || err.message || 'Unknown error'), 'danger')
  }
}

async function doSetSpeed(mode) {
  try { speed.value = mode; await api.setSpeed(simId, mode) }
  catch (err) { console.error('Speed change failed:', err) }
}

async function stopSim() {
  try {
    await api.stop(simId)
    addToast('Stopping simulation...', 'info')
    setTimeout(() => { if (phase.value === 'running') { phase.value = 'complete'; if (eventSource) eventSource.close() } }, 5000)
  } catch (err) { addToast('Failed to stop simulation', 'danger') }
}

async function cancelSim() {
  cancelling.value = true
  try {
    await api.cancel(simId)
    if (eventSource) { eventSource.close(); eventSource = null }
    localStorage.removeItem('mirosociety_active_sim')
    router.push('/')
  } catch (err) {
    addToast('Failed to cancel: ' + (err.response?.data?.detail || err.message || 'Unknown error'), 'danger')
    cancelling.value = false
  }
}

async function doInject(text) {
  if (!text.trim()) return
  try { await api.inject(simId, text); addToast('Event injected', 'warning'); showInject.value = false }
  catch (err) { addToast('Failed to inject event', 'danger') }
}

function openFork() { showFork.value = true }

async function doFork({ day, changes }) {
  if (!day || day < 1) { addToast('Please select a valid day to fork from', 'warning'); return }
  forking.value = true
  try {
    const result = await api.fork(simId, day, changes || null)
    showFork.value = false
    addToast(`Fork created at day ${day}. Opening...`, 'info')
    router.push(`/simulation/${result.simulation_id}`)
  } catch (e) {
    addToast('Fork failed: ' + (e.response?.data?.detail || e.message || 'Unknown error'), 'danger')
  }
  forking.value = false
}

async function sendChat(question) {
  if (!question.trim() || !selectedAgent.value || chatLoading.value) return
  const agentId = selectedAgent.value.id
  chatMessages.value.push({ role: 'user', text: question })
  chatLoading.value = true
  try {
    const data = await api.interview(simId, agentId, question)
    chatMessages.value.push({ role: 'agent', text: data.response || 'No response.' })
  } catch { chatMessages.value.push({ role: 'agent', text: "Sorry, I can't respond right now..." }) }
  finally { chatLoading.value = false }
}

// ---- SCROLL ----
const userScrolledUp = ref(false)

function onFeedScroll() {
  if (!feedRef.value) return
  const el = feedRef.value
  userScrolledUp.value = (el.scrollHeight - el.scrollTop - el.clientHeight) > 150
}

function scrollToBottom() {
  if (feedRef.value) feedRef.value.scrollTop = feedRef.value.scrollHeight
}

watch(rawEvents, async () => {
  await nextTick()
  if (feedRef.value && !userScrolledUp.value) feedRef.value.scrollTop = feedRef.value.scrollHeight
}, { deep: true })

watch(selectedAgentId, () => updateNodeAppearance())

// ---- KEYBOARD SHORTCUTS ----
function handleKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

  if (e.key === 'Escape' && phase.value === 'generating') { cancelSim(); return }

  if (phase.value !== 'running' && phase.value !== 'complete') return

  if (e.key === ' ' && phase.value === 'running') { e.preventDefault(); togglePause() }
  else if (e.key === '1') doSetSpeed('live')
  else if (e.key === '2') doSetSpeed('fast_forward')
  else if (e.key === '3') doSetSpeed('jump')
  else if (e.key === 'Escape') { selectedAgentId.value = null; showInject.value = false; showFork.value = false; showShortcuts.value = false }
  else if (e.key === 'i' || e.key === 'I') { if (phase.value === 'running') showInject.value = true }
  else if (e.key === 'f' || e.key === 'F') openFork()
  else if (e.key === '?') showShortcuts.value = true
}

// ---- RESIZE ----
function handleResize() {
  if ((phase.value === 'running' || phase.value === 'complete') && viewMode.value === 'map') {
    nextTick(() => initGraph())
  }
}

watch(viewMode, (v) => {
  if (v === 'map' && (phase.value === 'running' || phase.value === 'complete')) nextTick(() => initGraph())
})

// ---- SSE ----
onMounted(() => {
  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', handleKeydown)

  // Store active sim for navbar indicator
  localStorage.setItem('mirosociety_active_sim', JSON.stringify({ id: simId, name: '' }))

  const es = api.streamSimulation(simId)
  eventSource = es

  es.addEventListener('status', (e) => {
    const d = JSON.parse(e.data)
    statusText.value = (d.status || '').replace(/_/g, ' ')
  })

  es.addEventListener('world_ready', (e) => {
    const bp = JSON.parse(e.data)
    worldName.value = bp.name || ''
    worldDescription.value = bp.description || ''
    locations.value = bp.locations || []
    statusText.value = 'World created. Generating citizens...'
    advanceGenStep('world')
    advanceGenStep('locations')
    localStorage.setItem('mirosociety_active_sim', JSON.stringify({ id: simId, name: bp.name || '' }))
  })

  es.addEventListener('citizen_generated', (e) => {
    const c = JSON.parse(e.data)
    citizens.value.push(c)
    agentMap[c.id] = c
    if (genSteps.value.find(s => s.id === 'citizens')?.status === 'pending') advanceGenStep('locations')
  })

  es.addEventListener('round_complete', (e) => {
    const rd = JSON.parse(e.data)

    if (phase.value !== 'running') {
      phase.value = 'running'
      advanceGenStep('citizens')
      advanceGenStep('start')
      nextTick(() => initGraph())
    }

    currentDay.value = rd.day || 0
    currentTimeOfDay.value = rd.time_of_day || 'morning'

    if (rd.metrics) { prevMetrics.value = { ...metrics.value }; metrics.value = rd.metrics }

    if (rd.agents) {
      for (const snap of rd.agents) {
        if (agentMap[snap.id]) {
          agentMap[snap.id].emotional_state = snap.emotional_state
          agentMap[snap.id].faction = snap.faction
          if (snap.location) agentMap[snap.id].location = snap.location
          if (snap.core_memory) agentMap[snap.id].core_memory = snap.core_memory
          if (snap.beliefs) agentMap[snap.id].beliefs = snap.beliefs
          if (snap.working_memory) agentMap[snap.id].working_memory = snap.working_memory
          if (snap.goals) agentMap[snap.id].goals = snap.goals
          if (simulation) addSimulationNode(snap.id)
        }
      }
      updateNodeAppearance()
    }

    if (rd.institutions) institutions.value = rd.institutions
    processRound(rd.actions || [], rd.reactions || [], rd.tension_event, rd.narrative)
  })

  es.addEventListener('simulation_complete', () => {
    phase.value = 'complete'
    Object.keys(speechBubbles).forEach(k => delete speechBubbles[k])
    Object.keys(actorFlash).forEach(k => delete actorFlash[k])
    addToast('Simulation complete', 'info')
    localStorage.removeItem('mirosociety_active_sim')
    es.close()
    eventSource = null
  })

  es.addEventListener('cancelled', () => {
    localStorage.removeItem('mirosociety_active_sim')
    es.close()
    eventSource = null
    router.push('/')
  })

  es.addEventListener('error', (e) => { console.error('SSE error:', e) })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
  if (eventSource) { eventSource.close(); eventSource = null }
  if (simulation) { simulation.stop(); simulation = null }
})
</script>

<style scoped>
@keyframes speech-pop {
  0% { opacity: 0; transform: translateY(4px) scale(0.9); }
  10% { opacity: 1; transform: translateY(0) scale(1); }
  75% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-6px) scale(0.95); }
}
.speech-bubble-anim {
  animation: speech-pop 5s ease-out forwards;
}
.view-toggle {
  isolation: isolate;
}
.view-toggle-indicator {
  pointer-events: none;
}
</style>
