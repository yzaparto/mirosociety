<template>
  <Transition name="slide-panel">
    <div v-if="agent" class="w-72 shrink-0 border-l border-gray-200 overflow-y-auto bg-[#fafafa]">
      <div class="p-4 space-y-1">
        <!-- Header -->
        <div class="flex justify-between items-start">
          <div>
            <div class="flex items-center gap-2">
              <MoodDot :state="agent.emotional_state" size="md" />
              <h3 class="font-semibold text-sm">{{ agent.name }}</h3>
            </div>
            <p class="text-[11px] text-slate-500 mt-0.5">{{ agent.role }}, {{ agent.age }}</p>
          </div>
          <button @click="$emit('close')" class="text-slate-400 hover:text-slate-700 text-xs p-1 rounded hover:bg-gray-100 transition-colors">✕</button>
        </div>

        <!-- Tabs -->
        <div class="flex gap-0.5 bg-gray-100 rounded-lg p-0.5 mt-3">
          <button
            v-for="t in tabs"
            :key="t.id"
            @click="activeTab = t.id"
            :class="[
              'flex-1 text-[10px] py-1.5 rounded-md transition-all duration-150 font-medium',
              activeTab === t.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            ]"
          >
            {{ t.label }}
          </button>
        </div>

        <!-- Profile Tab -->
        <div v-if="activeTab === 'profile'" class="space-y-3 pt-2">
          <p class="text-[11px] text-slate-500 leading-relaxed">{{ agent.background }}</p>
          <div class="text-[11px]">
            <MoodDot :state="agent.emotional_state" size="xs" class="inline-block mr-1 align-middle" />
            <span class="text-slate-500 italic">{{ agent.emotional_state }}</span>
            <span v-if="agent.faction" class="ml-2 px-1.5 py-0.5 rounded bg-violet-50 text-violet-600 text-[10px]">{{ agent.faction }}</span>
          </div>
          <div v-if="agent.personality">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Personality</div>
            <div v-for="(val, key) in agent.personality" :key="key" class="flex items-center gap-2 mb-1.5">
              <span class="text-[10px] text-slate-500 w-20 capitalize">{{ key }}</span>
              <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div class="h-full bg-emerald-600/60 rounded-full transition-all duration-500" :style="{ width: (val * 100) + '%' }"></div>
              </div>
              <span class="text-[9px] text-slate-400 w-6 text-right font-mono">{{ (val * 100).toFixed(0) }}</span>
            </div>
          </div>
        </div>

        <!-- Life Tab -->
        <div v-if="activeTab === 'life'" class="space-y-3 pt-2">
          <div v-if="agent.life_state">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Life Situation</div>
            <div v-for="domain in ['finances', 'career', 'health']" :key="domain" class="flex items-center gap-2 mb-2">
              <span class="text-[10px] text-slate-500 w-16 capitalize">{{ domain }}</span>
              <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500"
                  :class="domainColor(agent.life_state[domain])"
                  :style="{ width: (agent.life_state[domain] * 100) + '%' }"></div>
              </div>
              <span class="text-[9px] text-slate-400 w-16 text-right">{{ domainLabel(agent.life_state[domain]) }}</span>
            </div>
          </div>

          <div v-if="agent.life_state?.family?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Family</div>
            <div v-for="f in agent.life_state.family" :key="f.name" class="text-[11px] text-slate-600 py-0.5 flex items-center gap-1.5">
              <span class="text-slate-400">•</span>
              <span>{{ f.name }}</span>
              <span class="text-slate-400">({{ f.relation }}, {{ f.age }})</span>
              <span v-if="f.status !== 'healthy'" class="text-[9px] px-1.5 py-0.5 rounded"
                :class="f.status === 'ill' ? 'bg-red-50 text-red-600' : f.status === 'estranged' ? 'bg-amber-50 text-amber-600' : 'bg-gray-100 text-gray-500'">
                {{ f.status }}
              </span>
            </div>
          </div>

          <div v-if="agent.life_state?.pressures?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Pressures</div>
            <div v-for="p in agent.life_state.pressures" :key="p.description" class="mb-2 pl-2.5 border-l-2 border-amber-300">
              <p class="text-[11px] text-slate-700 leading-relaxed">{{ p.description }}</p>
              <div class="flex items-center gap-2 mt-1">
                <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                  <div class="h-full bg-amber-400 rounded-full" :style="{ width: (p.severity * 100) + '%' }"></div>
                </div>
                <span class="text-[9px] text-slate-400">{{ (p.severity * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <div v-if="agent.life_state?.childhood_summary">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">History</div>
            <p class="text-[11px] text-slate-500 leading-relaxed italic mb-2">{{ agent.life_state.childhood_summary }}</p>
            <div v-if="agent.life_state.formative_events?.length">
              <div v-for="e in agent.life_state.formative_events" :key="e.age_at_event" class="text-[11px] text-slate-600 py-1 pl-2.5 border-l-2 border-gray-200 mb-1">
                <span class="text-slate-400 text-[9px]">Age {{ e.age_at_event }}:</span> {{ e.description }}
              </div>
            </div>
          </div>

          <div v-if="agent.life_state?.life_log?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Life Events</div>
            <div v-for="log in agent.life_state.life_log.slice(-5)" :key="log" class="text-[11px] text-slate-500 py-0.5">{{ log }}</div>
          </div>

          <div v-if="!agent.life_state" class="text-[11px] text-slate-400 italic py-4 text-center">
            No life history available
          </div>
        </div>

        <!-- Memory Tab -->
        <div v-if="activeTab === 'memory'" class="space-y-3 pt-2">
          <div v-if="agent.beliefs?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Beliefs</div>
            <div v-for="b in agent.beliefs.slice(0, 6)" :key="b" class="text-[11px] text-slate-700 py-1 pl-2.5 border-l-2 border-gray-200 mb-0.5">{{ b }}</div>
          </div>
          <div v-if="agent.core_memory?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Remembers</div>
            <div v-for="m in agent.core_memory.slice(0, 5)" :key="m" class="text-[11px] text-slate-500 py-1 flex gap-1.5">
              <span class="text-slate-400 shrink-0">•</span>
              <span>{{ m }}</span>
            </div>
          </div>
          <div v-if="agent.goals?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Goals</div>
            <div v-for="g in agent.goals.slice(0, 4)" :key="g" class="text-[11px] text-slate-500 py-0.5">{{ g }}</div>
          </div>
          <div v-if="!agent.beliefs?.length && !agent.core_memory?.length && !agent.goals?.length" class="text-[11px] text-slate-400 italic py-4 text-center">
            No memories yet...
          </div>
        </div>

        <!-- Chat Tab -->
        <div v-if="activeTab === 'chat'" class="pt-2">
          <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Ask {{ agent.name?.split(' ')[0] }}</div>
          <div v-if="chatMessages.length" class="space-y-1.5 max-h-48 overflow-y-auto mb-3 scroll-smooth">
            <div
              v-for="(msg, i) in chatMessages"
              :key="i"
              :class="[
                'text-[11px] px-2.5 py-2 rounded-lg leading-relaxed',
                msg.role === 'user'
                  ? 'bg-emerald-50 border border-emerald-300 ml-4 text-right text-slate-700'
                  : 'bg-gray-100 border border-gray-200 mr-4 text-slate-800'
              ]"
            >
              {{ msg.text }}
            </div>
          </div>
          <div v-if="chatLoading" class="flex items-center gap-2 text-[10px] text-slate-500 mb-2">
            <div class="w-1 h-1 bg-slate-500 rounded-full animate-pulse"></div>
            Thinking...
          </div>
          <div class="flex gap-1.5">
            <input
              v-model="localChatInput"
              @keyup.enter="sendChat"
              :disabled="chatLoading"
              placeholder="Ask something..."
              class="flex-1 bg-white border border-gray-300 rounded-lg px-2.5 py-2 text-[11px] outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-600/30 placeholder-slate-400 disabled:opacity-50 transition-colors"
            />
            <button
              @click="sendChat"
              :disabled="chatLoading || !localChatInput.trim()"
              class="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-[11px] text-white shrink-0 disabled:opacity-40 transition-colors active:scale-[0.97]"
            >→</button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref } from 'vue'
import MoodDot from './MoodDot.vue'

defineProps({
  agent: { type: Object, default: null },
  chatMessages: { type: Array, default: () => [] },
  chatLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'chat'])

const activeTab = ref('profile')
const localChatInput = ref('')

const tabs = [
  { id: 'profile', label: 'Profile' },
  { id: 'life', label: 'Life' },
  { id: 'memory', label: 'Memory' },
  { id: 'chat', label: 'Chat' },
]

function domainColor(value) {
  if (value < 0.25) return 'bg-red-400'
  if (value < 0.5) return 'bg-amber-400'
  if (value < 0.75) return 'bg-emerald-400'
  return 'bg-emerald-600'
}

function domainLabel(value) {
  if (value < 0.2) return 'desperate'
  if (value < 0.35) return 'struggling'
  if (value < 0.5) return 'tight'
  if (value < 0.65) return 'stable'
  if (value < 0.8) return 'comfortable'
  return 'thriving'
}

function sendChat() {
  if (!localChatInput.value.trim()) return
  emit('chat', localChatInput.value)
  localChatInput.value = ''
}
</script>

<style scoped>
.slide-panel-enter-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.slide-panel-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.slide-panel-enter-from {
  transform: translateX(100%);
  opacity: 0;
}
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
