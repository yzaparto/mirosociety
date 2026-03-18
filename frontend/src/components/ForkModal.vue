<template>
  <BaseModal :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <div class="p-6 space-y-5">
      <div>
        <h3 class="font-semibold text-lg">Fork Simulation</h3>
        <p class="text-sm text-slate-400 mt-1">Create an alternate timeline from a specific day. The fork copies all state up to that day, then applies your changes.</p>
      </div>

      <div>
        <label class="text-xs text-slate-500 block mb-1.5">Fork at day</label>
        <input
          v-model.number="localDay"
          type="number"
          :min="1"
          :max="maxDay"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-colors"
        />
      </div>

      <div>
        <label class="text-xs text-slate-500 block mb-1.5">What changes in this timeline?</label>
        <textarea
          v-model="localChanges"
          rows="3"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 resize-none transition-colors"
          placeholder="Describe what's different in this fork..."
        ></textarea>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="preset in presets"
          :key="preset"
          @click="localChanges = preset"
          class="text-[11px] px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-400 hover:text-blue-400 hover:border-blue-500 hover:bg-blue-950/30 transition-all active:scale-[0.97]"
        >
          {{ preset }}
        </button>
      </div>

      <div class="flex gap-2 justify-end pt-2">
        <button @click="$emit('update:modelValue', false)" class="btn-secondary text-sm">Cancel</button>
        <button
          @click="fork"
          :disabled="forking"
          class="px-5 py-2.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm font-medium transition-colors disabled:opacity-50 active:scale-[0.97]"
        >
          {{ forking ? 'Forking...' : 'Create Fork' }}
        </button>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  maxDay: { type: Number, default: 1 },
  initialDay: { type: Number, default: 1 },
  forking: { type: Boolean, default: false },
  presets: { type: Array, default: () => [
    'What if the price was 20% higher?',
    'What if a competitor launched the same day?',
    'What if we did a gradual rollout?',
    'What if we kept the old option available?',
    'What if an influencer publicly criticized it?',
  ]},
})

const emit = defineEmits(['update:modelValue', 'fork'])

const localDay = ref(props.initialDay)
const localChanges = ref('')

watch(() => props.initialDay, (v) => { localDay.value = v })
watch(() => props.modelValue, (v) => {
  if (v) {
    localDay.value = props.initialDay
    localChanges.value = ''
  }
})

function fork() {
  emit('fork', { day: localDay.value, changes: localChanges.value })
}
</script>
