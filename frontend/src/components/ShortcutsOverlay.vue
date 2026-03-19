<template>
  <BaseModal :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="sm">
    <div class="p-5 space-y-4">
      <h3 class="font-semibold text-sm">Keyboard Shortcuts</h3>
      <div class="space-y-2">
        <div v-for="s in shortcuts" :key="s.key" class="flex items-center justify-between text-sm">
          <span class="text-slate-500">{{ s.label }}</span>
          <kbd class="bg-gray-100 border border-gray-300 rounded px-2 py-0.5 text-[11px] font-mono text-slate-700">{{ s.key }}</kbd>
        </div>
      </div>
      <button @click="$emit('update:modelValue', false)" class="btn-secondary text-sm w-full">Close</button>
    </div>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

defineProps({ modelValue: { type: Boolean, default: false } })
defineEmits(['update:modelValue'])

const shortcuts = [
  { key: 'Space', label: 'Pause / Resume' },
  { key: '1', label: 'Normal speed (1×)' },
  { key: '2', label: 'Fast forward (5×)' },
  { key: '3', label: 'Jump (10×)' },
  { key: 'Tab', label: 'Cycle view (Map / Split / Feed)' },
  { key: 'I', label: 'Inject event' },
  { key: 'F', label: 'Fork simulation' },
  { key: 'Escape', label: 'Deselect agent / Close modal' },
  { key: '?', label: 'Show shortcuts' },
]
</script>
