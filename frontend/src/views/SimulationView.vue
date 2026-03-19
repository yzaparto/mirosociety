<template>
  <div class="h-screen flex flex-col overflow-hidden bg-[#fafafa] text-slate-800">
    <!-- Toasts -->
    <ToastContainer :toasts="toasts" @dismiss="dismissToast" />

    <!-- Shortcuts overlay -->
    <ShortcutsOverlay v-model="showShortcuts" />

    <!-- Top bar -->
    <div class="h-12 border-b border-gray-200/80 flex items-center px-5 gap-3 shrink-0 bg-white">
      <router-link to="/" class="text-slate-400 hover:text-slate-700 transition-colors">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
      </router-link>
      <h1 class="font-semibold text-sm text-slate-900 truncate">{{ worldName || 'Generating...' }}</h1>
      <div v-if="currentDay" class="text-[11px] text-slate-500 bg-gray-100 px-2.5 py-1 rounded-md font-mono">
        Day {{ currentDay }} · {{ currentTimeOfDay }}
      </div>
      <div v-if="phase === 'generating'" class="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1">
        <div class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
        <span class="text-[11px] text-emerald-700 font-medium">Generating</span>
      </div>
      <div v-if="phase === 'running'" class="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1">
        <div class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
        <span class="text-[11px] text-emerald-700 font-medium">Live</span>
      </div>
      <div v-if="phase === 'complete'" class="text-[11px] text-slate-500 bg-gray-100 border border-gray-200 px-2.5 py-1 rounded-md font-medium">Complete</div>

      <div class="flex-1"></div>

      <!-- Controls (inline when running) -->
      <template v-if="phase === 'running' || phase === 'complete'">
        <div class="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          <button @click="viewMode = 'map'"
            :class="['text-[11px] px-2.5 py-1 rounded-md transition-all duration-150 font-medium', viewMode === 'map' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700']">
            Map
          </button>
          <button v-if="isWideScreen" @click="viewMode = 'split'"
            :class="['text-[11px] px-2.5 py-1 rounded-md transition-all duration-150 font-medium', viewMode === 'split' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700']">
            Split
          </button>
          <button @click="viewMode = 'feed'"
            :class="['text-[11px] px-2.5 py-1 rounded-md transition-all duration-150 font-medium', viewMode === 'feed' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700']">
            Feed
          </button>
        </div>

        <div class="w-px h-4 bg-gray-200"></div>

        <template v-if="phase === 'running'">
          <div class="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
            <button v-for="s in speeds" :key="s.id" @click="doSetSpeed(s.id)"
              :class="['text-[11px] px-2 py-1 rounded-md transition-all duration-150 font-medium', speed === s.id ? s.active : 'text-slate-500 hover:text-slate-700']"
              :title="s.title">
              {{ s.label }}
            </button>
          </div>

          <div class="w-px h-4 bg-gray-200"></div>

          <button @click="togglePause"
            class="text-[11px] px-2.5 py-1 rounded-md hover:bg-gray-100 text-slate-600 hover:text-slate-900 transition-colors font-medium"
            title="Space">
            {{ paused ? 'Resume' : 'Pause' }}
          </button>
          <button @click="showInject = true"
            class="text-[11px] px-2.5 py-1 rounded-md hover:bg-amber-50 text-amber-600 hover:text-amber-700 transition-colors font-medium"
            title="I">
            Inject
          </button>
          <button @click="openFork()"
            class="text-[11px] px-2.5 py-1 rounded-md hover:bg-blue-50 text-blue-600 hover:text-blue-700 transition-colors font-medium"
            title="F">
            Fork
          </button>
          <button @click="stopSim"
            class="text-[11px] px-2.5 py-1 rounded-md hover:bg-red-50 text-red-500 hover:text-red-600 transition-colors font-medium">
            Stop
          </button>
        </template>
        <template v-if="phase === 'complete'">
          <button @click="openFork()" class="text-[11px] px-2.5 py-1 rounded-md hover:bg-blue-50 text-blue-600 font-medium transition-colors">Fork</button>
          <router-link :to="`/report/${simId}`" class="text-[11px] px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors shadow-sm">View Report →</router-link>
        </template>
      </template>

      <button @click="showShortcuts = true" class="text-slate-400 hover:text-slate-600 transition-colors" title="Keyboard shortcuts">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"/></svg>
      </button>
    </div>

    <!-- ===== GENERATION PHASE ===== -->
    <div v-if="phase === 'generating'" class="flex-1 relative overflow-hidden">
      <!-- Background swarm of citizens floating -->
      <GenerationSwarm :citizens="citizens" />

      <!-- Centered card overlay -->
      <div class="absolute inset-0 z-20 flex items-center justify-center p-6 pointer-events-none">
        <div class="max-w-lg w-full bg-white/95 backdrop-blur-md rounded-2xl shadow-xl shadow-black/8 border border-gray-200/60 overflow-hidden pointer-events-auto">
          <!-- Header bar -->
          <div class="flex items-center justify-between px-6 pt-5 pb-0">
            <div>
              <h3 class="text-base font-semibold text-slate-800">Setting up simulation</h3>
              <p class="text-xs text-slate-400 mt-0.5">Building your world...</p>
            </div>
            <button
              @click="cancelSim"
              :disabled="cancelling"
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors active:scale-95 disabled:opacity-40"
              :title="cancelling ? 'Cancelling...' : 'Cancel'"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>

          <!-- Progress stepper -->
          <div class="px-6 py-5">
            <div class="relative space-y-0">
              <div v-for="(step, i) in genSteps" :key="step.id"
                :class="['flex items-start gap-3 transition-all duration-500 relative', { 'opacity-35': step.status === 'pending' }]"
                :style="{ transitionDelay: (i * 60) + 'ms' }">
                <div class="flex flex-col items-center shrink-0">
                  <div v-if="step.status === 'done'" class="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center">
                    <svg class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                  </div>
                  <div v-else-if="step.status === 'active'" class="w-6 h-6 rounded-full border-2 border-emerald-400 flex items-center justify-center">
                    <div class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
                  </div>
                  <div v-else class="w-6 h-6 rounded-full border-2 border-gray-200"></div>
                  <div v-if="i < genSteps.length - 1"
                    :class="['w-0.5 h-5 my-0.5 rounded-full transition-colors duration-300',
                      step.status === 'done' ? 'bg-emerald-300' : 'bg-gray-200']">
                  </div>
                </div>
                <span :class="['text-sm pt-0.5', step.status === 'active' ? 'text-emerald-600 font-medium' : step.status === 'done' ? 'text-slate-600' : 'text-slate-400']">
                  {{ step.label }}
                </span>
              </div>
            </div>
          </div>

          <!-- World info (revealed when ready) -->
          <Transition name="feed">
            <div v-if="worldName" class="border-t border-gray-100 px-6 py-5 space-y-3">
              <h2 class="text-xl font-bold text-slate-800">{{ worldName }}</h2>
              <p class="text-slate-500 text-sm leading-relaxed">{{ worldDescription }}</p>
              <div v-if="locations.length" class="flex flex-wrap gap-1.5 pt-1">
                <TransitionGroup name="list">
                  <span v-for="loc in locations" :key="loc.id"
                    class="text-[11px] px-2.5 py-1 rounded-full bg-slate-50 border border-gray-200 text-slate-500">
                    {{ locIcon(loc.type) }} {{ loc.name }}
                  </span>
                </TransitionGroup>
              </div>

              <!-- Citizens counter -->
              <div v-if="citizens.length" class="pt-2">
                <p class="text-[11px] text-slate-400 font-medium">{{ citizens.length }} citizens generated — appearing behind this card</p>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- ===== SIMULATION PHASE ===== -->
    <div v-if="phase === 'running' || phase === 'complete'" class="flex-1 flex overflow-hidden">

      <!-- ========== MAP VIEW ========== -->
      <template v-if="viewMode === 'map'">
        <div class="flex-1 flex flex-col overflow-hidden">
          <div class="flex-1 relative overflow-hidden bg-white" ref="graphContainer">
            <svg ref="graphSvg" class="w-full h-full"></svg>

            <!-- Speech bubbles -->
            <div v-for="(text, agentId) in speechBubbles" :key="agentId"
              class="fixed z-[60] speech-bubble-anim pointer-events-none"
              :style="getNodeBubbleStyle(agentId)">
              <div :class="['text-[11px] px-3 py-2 rounded-xl shadow-lg max-w-[240px] leading-snug',
                speechBubbleClass(agentMap[agentId]?.emotional_state)]">
                "{{ text }}"
              </div>
            </div>

            <!-- Hover tooltip -->
            <Transition name="feed">
              <div v-if="hoveredAgentId && agentMap[hoveredAgentId]"
                class="fixed z-[55] pointer-events-none"
                :style="getNodeTooltipStyle(hoveredAgentId)">
                <div class="bg-white border border-gray-200 rounded-xl shadow-lg px-3.5 py-3 min-w-[190px] max-w-[260px]">
                  <div class="flex items-center gap-2 mb-1.5">
                    <MoodDot :state="agentMap[hoveredAgentId].emotional_state" />
                    <span class="text-xs font-semibold text-slate-900">{{ agentMap[hoveredAgentId].name }}</span>
                    <span class="text-[10px] text-slate-400">{{ agentMap[hoveredAgentId].role }}</span>
                  </div>
                  <div class="text-[11px] text-slate-500 italic capitalize">{{ agentMap[hoveredAgentId].emotional_state }}</div>
                  <div v-if="agentMap[hoveredAgentId].faction" class="text-[10px] text-violet-600 mt-0.5 font-medium">{{ agentMap[hoveredAgentId].faction }}</div>
                  <div v-if="agentLastAction[hoveredAgentId]" class="text-[11px] text-slate-700 mt-2 pt-2 border-t border-gray-100">
                    {{ agentLastAction[hoveredAgentId] }}
                  </div>
                </div>
              </div>
            </Transition>

            <!-- Zoom controls -->
            <div class="absolute bottom-4 right-4 flex flex-col gap-1 z-20">
              <button @click="zoomIn" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-sm flex items-center justify-center" title="Zoom in">+</button>
              <button @click="zoomOut" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-sm flex items-center justify-center" title="Zoom out">−</button>
              <button @click="zoomReset" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-[10px] font-medium flex items-center justify-center" title="Reset zoom">R</button>
            </div>

            <!-- Legend & social link toggle -->
            <div class="absolute bottom-4 left-4 z-20 flex items-end gap-1.5">
              <div>
                <button @click="showLegend = !showLegend"
                  class="text-[10px] text-slate-500 hover:text-slate-700 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg px-2.5 py-1.5 transition-colors shadow-sm font-medium">
                  {{ showLegend ? '▼ Legend' : '▶ Legend' }}
                </button>
                <Transition name="feed">
                  <div v-if="showLegend" class="mt-1.5 bg-white border border-gray-200 rounded-xl p-3 shadow-lg space-y-2">
                    <div v-for="item in legendItems" :key="item.label" class="flex items-center gap-2">
                      <div :class="['w-2.5 h-2.5 rounded-full', item.color]"></div>
                      <span class="text-[10px] text-slate-600">{{ item.label }}</span>
                    </div>
                    <div class="border-t border-gray-100 pt-2 mt-2 space-y-1.5">
                      <div class="flex items-center gap-2">
                        <svg class="w-5 h-1.5" viewBox="0 0 20 6"><line x1="0" y1="3" x2="20" y2="3" stroke="#34d399" stroke-width="1.5" stroke-dasharray="3 3"/></svg>
                        <span class="text-[10px] text-slate-500">Positive bond</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <svg class="w-5 h-1.5" viewBox="0 0 20 6"><line x1="0" y1="3" x2="20" y2="3" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3 3"/></svg>
                        <span class="text-[10px] text-slate-500">Neutral bond</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <svg class="w-5 h-1.5" viewBox="0 0 20 6"><line x1="0" y1="3" x2="20" y2="3" stroke="#f87171" stroke-width="1.5" stroke-dasharray="3 3"/></svg>
                        <span class="text-[10px] text-slate-500">Negative bond</span>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
              <button @click="showSocialLinks = !showSocialLinks; renderSocialLinks()"
                :class="['text-[10px] bg-white/90 backdrop-blur-sm border rounded-lg px-2.5 py-1.5 transition-colors shadow-sm font-medium',
                  showSocialLinks ? 'text-emerald-600 border-emerald-300 hover:text-emerald-500' : 'text-slate-500 border-gray-200 hover:text-slate-700']">
                {{ showSocialLinks ? '◉ Bonds' : '○ Bonds' }}
              </button>
            </div>
          </div>

          <!-- Metrics bar at bottom -->
          <MetricsStrip :metrics="metrics" :prev-metrics="prevMetrics" :show-market="isMarketSim">
            <template #right>
              <div v-if="institutions.length" class="flex gap-2">
                <span v-for="inst in institutions" :key="inst.name" class="text-[10px] text-violet-600 bg-violet-50 border border-violet-200 px-2 py-0.5 rounded-md font-medium">
                  {{ inst.name }}
                </span>
              </div>
            </template>
          </MetricsStrip>
        </div>
      </template>

      <!-- ========== SPLIT VIEW ========== -->
      <template v-if="viewMode === 'split'">
        <!-- LEFT: Map -->
        <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
          <div class="flex-1 relative overflow-hidden bg-white" ref="splitGraphContainer">
            <svg ref="splitGraphSvg" class="w-full h-full"></svg>

            <!-- Speech bubbles -->
            <div v-for="(text, agentId) in speechBubbles" :key="agentId"
              class="fixed z-[60] speech-bubble-anim pointer-events-none"
              :style="getNodeBubbleStyle(agentId)">
              <div :class="['text-[11px] px-3 py-2 rounded-xl shadow-lg max-w-[240px] leading-snug',
                speechBubbleClass(agentMap[agentId]?.emotional_state)]">
                "{{ text }}"
              </div>
            </div>

            <!-- Hover tooltip -->
            <Transition name="feed">
              <div v-if="hoveredAgentId && agentMap[hoveredAgentId]"
                class="fixed z-[55] pointer-events-none"
                :style="getNodeTooltipStyle(hoveredAgentId)">
                <div class="bg-white border border-gray-200 rounded-xl shadow-lg px-3.5 py-3 min-w-[190px] max-w-[260px]">
                  <div class="flex items-center gap-2 mb-1.5">
                    <MoodDot :state="agentMap[hoveredAgentId].emotional_state" />
                    <span class="text-xs font-semibold text-slate-900">{{ agentMap[hoveredAgentId].name }}</span>
                    <span class="text-[10px] text-slate-400">{{ agentMap[hoveredAgentId].role }}</span>
                  </div>
                  <div class="text-[11px] text-slate-500 italic capitalize">{{ agentMap[hoveredAgentId].emotional_state }}</div>
                  <div v-if="agentMap[hoveredAgentId].faction" class="text-[10px] text-violet-600 mt-0.5 font-medium">{{ agentMap[hoveredAgentId].faction }}</div>
                  <div v-if="agentLastAction[hoveredAgentId]" class="text-[11px] text-slate-700 mt-2 pt-2 border-t border-gray-100">
                    {{ agentLastAction[hoveredAgentId] }}
                  </div>
                </div>
              </div>
            </Transition>

            <!-- Zoom controls -->
            <div class="absolute bottom-4 right-4 flex flex-col gap-1 z-20">
              <button @click="zoomIn" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-sm flex items-center justify-center" title="Zoom in">+</button>
              <button @click="zoomOut" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-sm flex items-center justify-center" title="Zoom out">−</button>
              <button @click="zoomReset" class="w-8 h-8 rounded-lg bg-white/90 backdrop-blur-sm border border-gray-200 text-slate-500 hover:text-slate-900 hover:bg-white shadow-sm transition-colors text-[10px] font-medium flex items-center justify-center" title="Reset zoom">R</button>
            </div>

            <!-- Legend & social link toggle -->
            <div class="absolute bottom-4 left-4 z-20 flex items-end gap-1.5">
              <button @click="showSocialLinks = !showSocialLinks; renderSocialLinks()"
                :class="['text-[10px] bg-white/90 backdrop-blur-sm border rounded-lg px-2.5 py-1.5 transition-colors shadow-sm font-medium',
                  showSocialLinks ? 'text-emerald-600 border-emerald-300' : 'text-slate-500 border-gray-200 hover:text-slate-700']">
                {{ showSocialLinks ? '◉ Bonds' : '○ Bonds' }}
              </button>
            </div>
          </div>

          <!-- Metrics bar at bottom -->
          <MetricsStrip :metrics="metrics" :prev-metrics="prevMetrics" :show-market="isMarketSim">
            <template #right>
              <div v-if="institutions.length" class="flex gap-2">
                <span v-for="inst in institutions" :key="inst.name" class="text-[10px] text-violet-600 bg-violet-50 border border-violet-200 px-2 py-0.5 rounded-md font-medium">
                  {{ inst.name }}
                </span>
              </div>
            </template>
          </MetricsStrip>
        </div>

        <!-- Divider -->
        <div class="w-px bg-gray-200 shrink-0"></div>

        <!-- RIGHT: Feed (no agent sidebar) -->
        <div class="w-[440px] shrink-0 flex flex-col overflow-hidden relative bg-[#fafafa]">
          <div class="flex-1 overflow-y-auto" ref="splitFeedRef" @scroll="onFeedScroll">
            <div class="px-5 py-4">
              <!-- Empty state -->
              <div v-if="!rawEvents.length" class="flex flex-col items-center justify-center py-20 text-slate-400">
                <div class="w-8 h-8 border-2 border-gray-300 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                <p class="text-sm">Waiting for the first day to begin...</p>
              </div>

              <template v-for="(group, gi) in groupedEvents" :key="gi">
                <div class="sticky top-0 z-10 py-2">
                  <div class="text-[11px] text-slate-500 font-semibold uppercase tracking-wider bg-[#fafafa]/95 backdrop-blur-sm py-1.5 px-2.5 rounded-lg inline-block border border-gray-100">
                    Day {{ group.day }} · {{ group.tod }}
                  </div>
                </div>
                <div class="mb-5 space-y-0.5">
                  <template v-for="(evt, ei) in group.events" :key="ei">
                    <div v-if="evt.type === 'life_event'" class="pl-3 py-2 border-l-2 border-dashed border-slate-300 bg-slate-50/50 rounded-r-lg">
                      <div class="flex items-center gap-1.5 mb-0.5">
                        <span class="text-slate-400 text-[10px]">⟡</span>
                        <span class="text-[10px] text-slate-500 font-medium">{{ evt.agent_name }}</span>
                        <span class="text-[10px] text-slate-400">experienced a life event</span>
                      </div>
                      <p class="text-[11px] text-slate-600 italic leading-relaxed pl-4">{{ evt.event_description }}</p>
                    </div>
                    <div v-else
                      :class="[
                        'py-2 px-3 rounded-lg text-[13px] leading-relaxed transition-colors',
                        evt.highlight ? 'bg-amber-50/80 border-l-2 border-amber-400' : 'border-l-2 border-transparent hover:bg-white hover:shadow-sm'
                      ]">
                      <span v-html="evt.html"></span>
                    </div>
                  </template>
                </div>
              </template>

              <div v-if="phase === 'complete' && rawEvents.length" class="text-center py-6 border-t border-gray-200 mt-4">
                <p class="text-slate-500 text-sm mb-3">The simulation has ended.</p>
                <router-link :to="`/report/${simId}`" class="btn-primary text-sm px-5 py-2.5">View Report →</router-link>
              </div>
            </div>
          </div>

          <!-- Scroll to bottom FAB -->
          <Transition name="feed">
            <button
              v-if="userScrolledUp && rawEvents.length"
              @click="scrollToBottom"
              class="absolute bottom-4 right-4 z-20 w-9 h-9 rounded-full bg-emerald-600 text-white flex items-center justify-center shadow-lg hover:bg-emerald-500 transition-colors text-sm active:scale-[0.95]"
            >
              ↓
            </button>
          </Transition>
        </div>
      </template>

      <!-- ========== FEED VIEW ========== -->
      <template v-if="viewMode === 'feed'">
        <!-- LEFT sidebar - Agent list -->
        <div class="w-64 shrink-0 border-r border-gray-100 flex flex-col overflow-hidden bg-white">
          <!-- Compact metrics -->
          <div class="px-3 py-2.5 border-b border-gray-100">
            <div class="grid grid-cols-5 gap-1.5">
              <div v-for="m in SOCIAL_METRICS" :key="m.key" class="text-center">
                <div class="text-[8px] text-slate-400 leading-none mb-1 flex items-center justify-center gap-0.5 uppercase tracking-wider font-medium">
                  {{ m.label.slice(0, 5) }}
                </div>
                <div class="h-1 bg-gray-100 rounded-full overflow-hidden">
                  <div :class="['h-full rounded-full transition-all duration-700', metricBarColorFn(m.key)]"
                    :style="{ width: ((metrics[m.key] ?? 0) * 100) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Search -->
          <div class="px-3 py-2 border-b border-gray-100">
            <input
              v-model="agentSearch"
              placeholder="Search citizens..."
              class="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-[11px] outline-none focus:border-emerald-500 focus:bg-white placeholder-slate-400 transition-all"
            />
          </div>

          <!-- Agent list -->
          <div class="flex-1 overflow-y-auto px-2 py-2">
            <div class="text-[9px] text-slate-400 uppercase tracking-wider px-2 py-1.5 font-semibold">Citizens ({{ filteredAgents.length }})</div>
            <div
              v-for="a in filteredAgents"
              :key="a.id"
              @click="selectAgent(a.id)"
              :class="[
                'flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-all duration-150 mb-0.5',
                selectedAgentId === a.id ? 'bg-emerald-50 border border-emerald-200' : 'hover:bg-gray-50 border border-transparent'
              ]"
            >
              <AgentAvatar :agent="a" :selected="selectedAgentId === a.id" size="sm" @click.stop="selectAgent(a.id)" />
              <div class="min-w-0 flex-1">
                <div class="text-[11px] font-medium text-slate-900 truncate">{{ a.name }}</div>
                <div class="text-[9px] text-slate-400 truncate italic">{{ a.emotional_state || a.role }}</div>
              </div>
              <div v-if="a.faction" class="text-[8px] text-violet-600 bg-violet-50 border border-violet-100 px-1.5 py-0.5 rounded-md shrink-0 font-medium">{{ a.faction }}</div>
            </div>
          </div>
        </div>

        <!-- CENTER: Event feed -->
        <div class="flex-1 flex flex-col overflow-hidden bg-[#fafafa]">
          <div class="flex-1 overflow-y-auto" ref="feedRef" @scroll="onFeedScroll">
            <div class="max-w-3xl mx-auto px-6 py-5">
              <!-- Empty state -->
              <div v-if="!rawEvents.length" class="flex flex-col items-center justify-center py-20 text-slate-400">
                <div class="w-8 h-8 border-2 border-gray-300 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                <p class="text-sm">Waiting for the first day to begin...</p>
              </div>

              <template v-for="(group, gi) in groupedEvents" :key="gi">
                <div class="sticky top-0 z-10 py-2">
                  <div class="text-[11px] text-slate-500 font-semibold uppercase tracking-wider bg-[#fafafa]/95 backdrop-blur-sm py-1.5 px-3 rounded-lg inline-block border border-gray-100">
                    Day {{ group.day }} · {{ group.tod }}
                  </div>
                </div>
                <div class="mb-6 space-y-1">
                  <template v-for="(evt, ei) in group.events" :key="ei">
                    <div v-if="evt.type === 'life_event'" class="pl-3 py-2 border-l-2 border-dashed border-slate-300 bg-slate-50/50 rounded-r-lg">
                      <div class="flex items-center gap-1.5 mb-0.5">
                        <span class="text-slate-400 text-[10px]">⟡</span>
                        <span class="text-[10px] text-slate-500 font-medium">{{ evt.agent_name }}</span>
                        <span class="text-[10px] text-slate-400">experienced a life event</span>
                      </div>
                      <p class="text-[11px] text-slate-600 italic leading-relaxed pl-4">{{ evt.event_description }}</p>
                    </div>
                    <div v-else
                      :class="[
                        'py-2.5 px-4 rounded-lg text-[13px] leading-relaxed transition-colors',
                        evt.highlight ? 'bg-amber-50/80 border-l-2 border-amber-400' : 'border-l-2 border-transparent hover:bg-white hover:shadow-sm'
                      ]">
                      <span v-html="evt.html"></span>
                    </div>
                  </template>
                </div>
              </template>

              <div v-if="phase === 'complete' && rawEvents.length" class="text-center py-8 border-t border-gray-200 mt-4">
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
              class="absolute bottom-14 right-8 z-20 w-9 h-9 rounded-full bg-emerald-600 text-white flex items-center justify-center shadow-lg hover:bg-emerald-500 transition-colors text-sm active:scale-[0.95]"
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
import GenerationSwarm from '../components/GenerationSwarm.vue'

const route = useRoute()
const router = useRouter()
const simId = route.params.id

// ---- STATE ----
const phase = ref('generating')
const isWideScreen = ref(window.innerWidth >= 1280)
const viewMode = ref(isWideScreen.value ? 'split' : 'map')
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
const demographics = ref(null)
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
const splitGraphContainer = ref(null)
const splitGraphSvg = ref(null)
const splitFeedRef = ref(null)

const activeGraphContainer = computed(() => viewMode.value === 'split' ? splitGraphContainer.value : graphContainer.value)
const activeGraphSvg = computed(() => viewMode.value === 'split' ? splitGraphSvg.value : graphSvg.value)
const activeFeedRef = computed(() => viewMode.value === 'split' ? splitFeedRef.value : feedRef.value)
const nodePositions = reactive({})
const graphEdges = ref([])
let simulation = null
let svgSelection = null
let gSelection = null
let linkGroup = null
let socialLinkGroup = null
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
  const containerEl = activeGraphContainer.value
  if (!pos || !containerEl) return null
  const rect = containerEl.getBoundingClientRect()
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
  const containerEl = activeGraphContainer.value
  const svgEl = activeGraphSvg.value
  if (!containerEl || !svgEl) return
  const container = containerEl
  const width = container.clientWidth
  const height = container.clientHeight

  svgSelection = d3.select(svgEl).attr('width', width).attr('height', height)
  svgSelection.selectAll('*').remove()

  const defs = svgSelection.append('defs')
  const pattern = defs.append('pattern').attr('id', 'dot-grid').attr('width', 32).attr('height', 32).attr('patternUnits', 'userSpaceOnUse')
  pattern.append('circle').attr('cx', 16).attr('cy', 16).attr('r', 0.6).attr('fill', '#e2e8f0')
  const dropShadow = defs.append('filter').attr('id', 'node-shadow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%')
  dropShadow.append('feDropShadow').attr('dx', 0).attr('dy', 1).attr('stdDeviation', 3).attr('flood-color', '#000').attr('flood-opacity', 0.08)

  svgSelection.append('rect').attr('width', width).attr('height', height).attr('fill', '#fff')
  svgSelection.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#dot-grid)')
  gSelection = svgSelection.append('g')
  socialLinkGroup = gSelection.append('g').attr('class', 'social-links')
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
    .force('collide', d3.forceCollide().radius(48))
    .force('x', d3.forceX(width / 2).strength(0.05))
    .force('y', d3.forceY(height / 2).strength(0.05))
    .on('tick', onSimTick)

  renderNodes()
  renderSocialLinks()
}

function onSimTick() {
  if (!simulation) return
  for (const n of simulation.nodes()) {
    nodePositions[n.id] = { x: n.x, y: n.y }
  }
  updateNodePositions()
  updateSocialLinkPositions()
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

  nodeG.append('circle').attr('class', 'select-ring').attr('r', 30).attr('fill', 'none').attr('stroke', 'transparent').attr('stroke-width', 2.5)
  nodeG.append('circle').attr('class', 'node-circle').attr('r', 24)
    .attr('fill', d => moodNodeFill(d.emotional_state))
    .attr('stroke', d => moodNodeStroke(d.emotional_state))
    .attr('stroke-width', 2).attr('opacity', 0.95)
    .attr('filter', 'url(#node-shadow)')
  nodeG.append('text').attr('class', 'node-initial').attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
    .attr('fill', '#fff').attr('font-size', '14px').attr('font-weight', '700').attr('pointer-events', 'none')
    .text(d => d.name.charAt(0))
  nodeG.append('text').attr('class', 'node-label').attr('text-anchor', 'middle').attr('y', 36)
    .attr('fill', '#475569').attr('font-size', '10px').attr('font-weight', '500').attr('pointer-events', 'none')
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
      .attr('stroke', selectedAgentId.value === d.id ? '#059669' : 'transparent')
      .attr('stroke-opacity', selectedAgentId.value === d.id ? 0.4 : 0)
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

const showSocialLinks = ref(true)

function buildSocialLinks() {
  const links = []
  const seen = new Set()
  for (const agent of Object.values(agentMap)) {
    if (!agent.social_connections) continue
    for (const edge of agent.social_connections) {
      if (edge.strength < 0.15) continue
      const key = [Math.min(agent.id, edge.target_id), Math.max(agent.id, edge.target_id)].join('-')
      if (seen.has(key)) continue
      seen.add(key)
      links.push({ source: agent.id, target: edge.target_id, strength: edge.strength, sentiment: edge.sentiment })
    }
  }
  return links
}

function socialLinkColor(sentiment) {
  if (sentiment >= 0.3) return '#6ee7b7'   // emerald for positive
  if (sentiment <= -0.3) return '#f87171'   // red for negative
  return '#64748b'                           // slate for neutral
}

function renderSocialLinks() {
  if (!socialLinkGroup || !showSocialLinks.value) { if (socialLinkGroup) socialLinkGroup.selectAll('*').remove(); return }
  const links = buildSocialLinks()

  const sel = socialLinkGroup.selectAll('line.social-edge').data(links, d => `${d.source}-${d.target}`)

  sel.exit().transition().duration(300).attr('stroke-opacity', 0).remove()

  sel.enter().append('line').attr('class', 'social-edge')
    .attr('stroke-dasharray', '4 4')
    .attr('stroke-linecap', 'round')
    .attr('stroke-opacity', 0)
    .merge(sel)
    .attr('stroke', d => socialLinkColor(d.sentiment))
    .attr('stroke-width', d => 0.5 + d.strength * 2)
    .transition().duration(600)
    .attr('stroke-opacity', d => 0.15 + d.strength * 0.35)

  updateSocialLinkPositions()
}

function updateSocialLinkPositions() {
  if (!socialLinkGroup) return
  socialLinkGroup.selectAll('line.social-edge')
    .attr('x1', d => nodePositions[d.source]?.x ?? 0)
    .attr('y1', d => nodePositions[d.source]?.y ?? 0)
    .attr('x2', d => nodePositions[d.target]?.x ?? 0)
    .attr('y2', d => nodePositions[d.target]?.y ?? 0)
}

function addSimulationNode(agentId) {
  const containerEl = activeGraphContainer.value
  if (!simulation || !containerEl) return
  const container = containerEl
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
  rawEvents.value.push({ day: currentDay.value, tod: currentTimeOfDay.value || 'morning', html, highlight: opts.highlight || false, location: opts.location || null, type: opts.type || 'default', agent_name: opts.agent_name || null, event_description: opts.event_description || null })
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
    enqueue(() => { addEvent(`<div class="text-slate-600 text-[12px] leading-relaxed italic border-l-2 border-slate-300 pl-3 my-1">${escapeHtml(narrative)}</div>`) })
  }

  for (const a of visibleActions) { enqueue(() => processOneAction(a)) }
  if (reactions) { for (const r of reactions) { enqueue(() => processOneReaction(r)) } }

  if (tensionEvent) {
    enqueue(() => {
      addEvent(`<span class="text-amber-600 font-medium">${tensionEvent}</span>`, { highlight: true })
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
    addEvent(`${who}: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>`, { location: loc })
    showSpeech(a.agent_id, a.speech)
    agentLastAction[a.agent_id] = `Said: "${a.speech.length > 50 ? a.speech.slice(0, 50) + '...' : a.speech}"`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    for (const hId of others.sort(() => Math.random() - 0.5).slice(0, Math.min(3, others.length))) {
      addGraphEdge(agentIdNum, hId, '#fbbf24')
    }
  } else if (at === 'SPEAK_PRIVATE' && a.speech) {
    const targetId = a.targets?.[0]
    const target = targetId != null ? nameSpan(agentNameById(targetId)) : 'someone'
    addEvent(`${who} whispered to ${target}: <span class="text-slate-500 italic">"${escapeHtml(a.speech)}"</span>`, { location: loc })
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
    addEvent(`${who} founded <span class="text-violet-600 font-medium">${gName}</span>`, { highlight: true, location: loc })
    addToast(`${a.agent_name} founded "${a.action_args?.name || 'a group'}"`, 'institution')
    agentLastAction[a.agent_id] = `Founded ${a.action_args?.name || 'a group'}`
  } else if (at === 'PROPOSE_RULE') {
    const content = a.action_args?.content || a.speech || 'a new rule'
    addEvent(`${who} proposed a rule: <span class="text-amber-600">"${escapeHtml(content)}"</span>`, { highlight: true, location: loc })
    agentLastAction[a.agent_id] = `Proposed: "${content.slice(0, 40)}..."`
  } else if (at === 'VOTE') {
    const vote = a.action_args?.vote === 'against' ? 'against' : 'for'
    addEvent(`${who} voted <span class="${vote === 'for' ? 'text-emerald-600' : 'text-red-600'} font-medium">${vote}</span>`, { location: loc })
    agentLastAction[a.agent_id] = `Voted ${vote}`
  } else if (at === 'PROTEST') {
    const target = escapeHtml(a.action_args?.target || 'the current order')
    const speechQuote = a.speech ? `: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} protested <span class="text-red-600">${target}</span>${speechQuote}`, { highlight: true, location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    addToast(`${a.agent_name} is protesting!`, 'warning')
    agentLastAction[a.agent_id] = `Protesting: ${(a.action_args?.target || 'the current order').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'DEFECT') {
    const how = escapeHtml(a.action_args?.how || 'broke the rules')
    const speechQuote = a.speech ? ` <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} <span class="text-red-600 font-medium">defected</span> — ${how}${speechQuote}`, { highlight: true, location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    addToast(`${a.agent_name} defected!`, 'danger')
    agentLastAction[a.agent_id] = `DEFECTED: ${(a.action_args?.how || 'broke the rules').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'BUILD') {
    const what = escapeHtml(a.action_args?.what || 'something')
    addEvent(`${who} built <span class="text-blue-600">${what}</span>`, { location: loc })
    agentLastAction[a.agent_id] = `Built ${a.action_args?.what || 'something'}`
  } else if (at === 'RECOMMEND') {
    const targetId = a.action_args?.target_id || a.targets?.[0]
    const target = targetId != null ? nameSpan(agentNameById(targetId)) : 'someone'
    const product = a.action_args?.product ? ` <span class="text-emerald-600">${escapeHtml(a.action_args.product)}</span>` : ''
    const speechQuote = a.speech ? `: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} recommended${product} to ${target}${speechQuote}`, { location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    if (targetId != null) addGraphEdge(agentIdNum, Number(targetId), '#6ee7b7')
    agentLastAction[a.agent_id] = `Recommended to ${targetId != null ? agentNameById(targetId) : 'someone'}`
  } else if (at === 'ABANDON') {
    const what = escapeHtml(a.action_args?.what || a.action_args?.product || 'their position')
    const reason = a.action_args?.reason ? ` — ${escapeHtml(a.action_args.reason)}` : ''
    const speechQuote = a.speech ? `: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} <span class="text-red-600">abandoned</span> ${what}${reason}${speechQuote}`, { highlight: true, location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    agentLastAction[a.agent_id] = `Abandoned: ${(a.action_args?.what || a.action_args?.product || 'their position').slice(0, 40)}`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#f87171')
  } else if (at === 'COMPARE') {
    const productA = a.action_args?.product_a || ''
    const productB = a.action_args?.product_b || ''
    const verdict = a.action_args?.verdict || ''
    const comparison = productA && productB ? ` <span class="text-sky-600">${escapeHtml(productA)}</span> vs <span class="text-sky-600">${escapeHtml(productB)}</span>` : ''
    const verdictText = verdict ? `: <span class="text-slate-600 italic">"${escapeHtml(verdict)}"</span>` : ''
    const speechQuote = !verdict && a.speech ? `: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} compared${comparison}${verdictText}${speechQuote}`, { location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    agentLastAction[a.agent_id] = `Comparing ${productA || 'options'}...`
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#94a3b8')
  } else if (at === 'PURCHASE') {
    const product = escapeHtml(a.action_args?.product || 'something')
    const speechQuote = a.speech ? `: <span class="text-slate-700">"${escapeHtml(a.speech)}"</span>` : ''
    addEvent(`${who} <span class="text-emerald-600 font-medium">purchased</span> ${product}${speechQuote}`, { location: loc })
    if (a.speech) showSpeech(a.agent_id, a.speech)
    agentLastAction[a.agent_id] = `Purchased ${(a.action_args?.product || 'something').slice(0, 40)}`
  } else if (at === 'RESEARCH') {
    const query = escapeHtml(a.action_args?.query || 'something')
    const findings = a.action_args?.findings
    const findingsText = findings ? ` — <span class="text-slate-500 italic">${escapeHtml(findings.slice(0, 120))}${findings.length > 120 ? '...' : ''}</span>` : ''
    addEvent(`${who} researched <span class="text-blue-600">${query}</span>${findingsText}`, { location: loc })
    agentLastAction[a.agent_id] = `Researched: ${(a.action_args?.query || 'something').slice(0, 40)}`
  } else if (at === 'OBSERVE') {
    addEvent(`<span class="text-slate-500">${escapeHtml(a.agent_name)} observed the scene</span>`, { location: loc })
    agentLastAction[a.agent_id] = 'Observing...'
    const others = Object.keys(agentMap).map(Number).filter(id => id !== agentIdNum)
    if (others.length) addGraphEdge(agentIdNum, others[Math.floor(Math.random() * others.length)], '#94a3b8')
  } else {
    addEvent(`${who}: ${escapeHtml(at)}`, { location: loc })
  }

  if (a.world_state_changes?.rule_passed) {
    addEvent(`<span class="text-emerald-600 font-medium">New community rule: "${escapeHtml(a.world_state_changes.rule_passed)}"</span>`, { highlight: true })
    addToast('New rule passed!', 'info')
  }
  if (a.world_state_changes?.rule_rejected) {
    addEvent(`<span class="text-red-600">Rule rejected: "${escapeHtml(a.world_state_changes.rule_rejected)}"</span>`)
  }
  if (a.world_state_changes?.institution_created) {
    addEvent(`<span class="text-violet-600 font-medium">New institution formed: ${escapeHtml(a.world_state_changes.institution_created)}</span>`, { highlight: true })
  }
}

function processOneReaction(r) {
  const loc = r.location || null
  if (r.reaction_type === 'respond' && r.content) {
    flashActor(r.agent_id)
    addEvent(`${nameSpan(r.agent_name)}: <span class="text-sky-600">"${escapeHtml(r.content)}"</span>`, { location: loc })
    showSpeech(r.agent_id, r.content)
    agentLastAction[r.agent_id] = `Responded: "${r.content.slice(0, 40)}..."`
  } else if (r.reaction_type === 'whisper' && r.content) {
    addEvent(`<span class="text-slate-500">${escapeHtml(r.agent_name)} whispered back: <span class="italic">"${escapeHtml(r.content)}"</span></span>`, { location: loc })
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
  const el = activeFeedRef.value
  if (!el) return
  userScrolledUp.value = (el.scrollHeight - el.scrollTop - el.clientHeight) > 150
}

function scrollToBottom() {
  const el = activeFeedRef.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(rawEvents, async () => {
  await nextTick()
  const el = activeFeedRef.value
  if (el && !userScrolledUp.value) el.scrollTop = el.scrollHeight
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
  else if (e.key === 'Tab') {
    e.preventDefault()
    const modes = isWideScreen.value ? ['map', 'split', 'feed'] : ['map', 'feed']
    const idx = modes.indexOf(viewMode.value)
    viewMode.value = modes[(idx + 1) % modes.length]
  }
}

// ---- RESIZE ----
function handleResize() {
  isWideScreen.value = window.innerWidth >= 1280
  if (!isWideScreen.value && viewMode.value === 'split') viewMode.value = 'map'
  const simActive = phase.value === 'running' || phase.value === 'complete'
  if (simActive && (viewMode.value === 'map' || viewMode.value === 'split')) {
    nextTick(() => initGraph())
  }
}

watch(viewMode, (v) => {
  if ((v === 'map' || v === 'split') && (phase.value === 'running' || phase.value === 'complete')) nextTick(() => initGraph())
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
    const existing = citizens.value.findIndex(x => x.id === c.id)
    if (existing >= 0) { citizens.value[existing] = c } else { citizens.value.push(c) }
    agentMap[c.id] = c
    if (genSteps.value.find(s => s.id === 'citizens')?.status === 'pending') advanceGenStep('locations')
  })

  es.addEventListener('round_complete', (e) => {
    const rd = JSON.parse(e.data)

    const needsInit = phase.value !== 'running'
    if (needsInit) {
      phase.value = 'running'
      advanceGenStep('citizens')
      advanceGenStep('start')
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
          if (snap.social_connections) agentMap[snap.id].social_connections = snap.social_connections
          if (simulation) addSimulationNode(snap.id)
        }
      }
    }

    if (rd.institutions) institutions.value = rd.institutions

    if (needsInit) {
      const roundActions = rd.actions || []
      const roundReactions = rd.reactions || []
      const roundTension = rd.tension_event
      const roundNarrative = rd.narrative
      const agentSnaps = rd.agents
      nextTick(() => {
        initGraph()
        if (agentSnaps) {
          for (const snap of agentSnaps) {
            if (agentMap[snap.id]) addSimulationNode(snap.id)
          }
        }
        updateNodeAppearance()
        renderSocialLinks()
        processRound(roundActions, roundReactions, roundTension, roundNarrative)
      })
    } else {
      if (rd.agents) {
        updateNodeAppearance()
        renderSocialLinks()
      }
      processRound(rd.actions || [], rd.reactions || [], rd.tension_event, rd.narrative)
    }
  })

  es.addEventListener('life_event', (e) => {
    const d = JSON.parse(e.data)
    if (d.day) currentDay.value = d.day
    if (d.time_of_day) currentTimeOfDay.value = d.time_of_day
    addEvent('', {
      type: 'life_event',
      agent_name: d.agent_name || agentNameById(d.agent_id),
      event_description: d.event_description || '',
    })
  })

  es.addEventListener('demographics_loaded', (e) => {
    const d = JSON.parse(e.data)
    demographics.value = d
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
</style>
