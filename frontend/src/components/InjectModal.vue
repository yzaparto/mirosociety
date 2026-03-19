<template>
  <BaseModal :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <div class="p-6 space-y-4">
      <h3 class="font-semibold text-lg">Inject Event</h3>
      <p class="text-sm text-slate-500">Describe something that happens in the world. Citizens will react.</p>
      <textarea
        v-model="text"
        rows="3"
        class="w-full bg-gray-100 border border-gray-300 rounded-lg p-3 text-sm outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 placeholder-slate-400 resize-none transition-colors"
        placeholder="A drought hits the settlement..."
        @keydown.meta.enter="inject"
        @keydown.ctrl.enter="inject"
      ></textarea>
      <div class="flex gap-2 justify-end">
        <button @click="$emit('update:modelValue', false)" class="btn-secondary text-sm">Cancel</button>
        <button
          @click="inject"
          :disabled="!text.trim()"
          class="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-white text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.97] shadow-sm"
        >
          Inject
        </button>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { ref } from 'vue'
import BaseModal from './BaseModal.vue'

defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'inject'])
const text = ref('')

function inject() {
  if (!text.value.trim()) return
  emit('inject', text.value)
  text.value = ''
}
</script>
