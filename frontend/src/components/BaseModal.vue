<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @keydown.escape="close"
      >
        <div class="absolute inset-0 bg-black/60" @click="close"></div>
        <div
          class="relative bg-white border border-gray-300 rounded-xl shadow-2xl w-full mx-4"
          :class="maxWidthClass"
          ref="contentRef"
        >
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  maxWidth: { type: String, default: 'md' },
})

const emit = defineEmits(['update:modelValue'])

const contentRef = ref(null)

const maxWidthClass = computed(() => ({
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
}[props.maxWidth] || 'max-w-md'))

function close() {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, async (val) => {
  if (val) {
    await nextTick()
    const focusable = contentRef.value?.querySelector('input, textarea, button, [tabindex]')
    focusable?.focus()
  }
})
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .relative {
  transform: scale(0.95) translateY(8px);
  opacity: 0;
}
.modal-leave-to .relative {
  transform: scale(0.95) translateY(8px);
  opacity: 0;
}
</style>
