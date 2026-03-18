<template>
  <Transition name="slide-panel">
    <div v-if="agent" class="w-72 shrink-0 border-l border-slate-800/60 overflow-y-auto bg-slate-950">
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
          <button @click="$emit('close')" class="text-slate-600 hover:text-slate-300 text-xs p-1 rounded hover:bg-slate-800 transition-colors">✕</button>
        </div>

        <!-- Tabs -->
        <div class="flex gap-0.5 bg-slate-800/40 rounded-lg p-0.5 mt-3">
          <button
            v-for="t in tabs"
            :key="t.id"
            @click="activeTab = t.id"
            :class="[
              'flex-1 text-[10px] py-1.5 rounded-md transition-colors font-medium',
              activeTab === t.id ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'
            ]"
          >
            {{ t.label }}
          </button>
        </div>

        <!-- Profile Tab -->
        <div v-if="activeTab === 'profile'" class="space-y-3 pt-2">
          <p class="text-[11px] text-slate-400 leading-relaxed">{{ agent.background }}</p>
          <div class="text-[11px]">
            <MoodDot :state="agent.emotional_state" size="xs" class="inline-block mr-1 align-middle" />
            <span class="text-slate-400 italic">{{ agent.emotional_state }}</span>
            <span v-if="agent.faction" class="ml-2 px-1.5 py-0.5 rounded bg-violet-900/40 text-violet-300 text-[10px]">{{ agent.faction }}</span>
          </div>
          <div v-if="agent.personality">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-2">Personality</div>
            <div v-for="(val, key) in agent.personality" :key="key" class="flex items-center gap-2 mb-1.5">
              <span class="text-[10px] text-slate-500 w-20 capitalize">{{ key }}</span>
              <div class="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div class="h-full bg-emerald-600/60 rounded-full transition-all duration-500" :style="{ width: (val * 100) + '%' }"></div>
              </div>
              <span class="text-[9px] text-slate-600 w-6 text-right font-mono">{{ (val * 100).toFixed(0) }}</span>
            </div>
          </div>
        </div>

        <!-- Memory Tab -->
        <div v-if="activeTab === 'memory'" class="space-y-3 pt-2">
          <div v-if="agent.beliefs?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Beliefs</div>
            <div v-for="b in agent.beliefs.slice(0, 6)" :key="b" class="text-[11px] text-slate-300 py-1 pl-2.5 border-l-2 border-slate-700/60 mb-0.5">{{ b }}</div>
          </div>
          <div v-if="agent.core_memory?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Remembers</div>
            <div v-for="m in agent.core_memory.slice(0, 5)" :key="m" class="text-[11px] text-slate-400 py-1 flex gap-1.5">
              <span class="text-slate-600 shrink-0">•</span>
              <span>{{ m }}</span>
            </div>
          </div>
          <div v-if="agent.goals?.length">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Goals</div>
            <div v-for="g in agent.goals.slice(0, 4)" :key="g" class="text-[11px] text-slate-400 py-0.5">{{ g }}</div>
          </div>
          <div v-if="!agent.beliefs?.length && !agent.core_memory?.length && !agent.goals?.length" class="text-[11px] text-slate-600 italic py-4 text-center">
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
                  ? 'bg-emerald-900/30 border border-emerald-800/30 ml-4 text-right text-slate-300'
                  : 'bg-slate-800/60 border border-slate-700/40 mr-4 text-slate-200'
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
              class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30 placeholder-slate-600 disabled:opacity-50 transition-colors"
            />
            <button
              @click="sendChat"
              :disabled="chatLoading || !localChatInput.trim()"
              class="px-3 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-[11px] text-white shrink-0 disabled:opacity-40 transition-colors active:scale-[0.97]"
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
  { id: 'memory', label: 'Memory' },
  { id: 'chat', label: 'Chat' },
]

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
