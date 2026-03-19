<template>
  <div class="fixed top-14 right-4 z-50 space-y-2 pointer-events-none">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="[
          'px-4 py-2.5 rounded-lg shadow-xl border text-sm max-w-sm pointer-events-auto flex items-center gap-2',
          typeClasses[toast.type] || typeClasses.info,
        ]"
      >
        <span class="flex-1">{{ toast.text }}</span>
        <button
          @click="$emit('dismiss', toast.id)"
          class="text-current opacity-40 hover:opacity-80 transition-opacity text-xs shrink-0 p-0.5"
        >
          ✕
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
defineProps({
  toasts: { type: Array, default: () => [] },
})

defineEmits(['dismiss'])

const typeClasses = {
  info: 'bg-emerald-50 border-emerald-300 text-emerald-800',
  danger: 'bg-red-50 border-red-300 text-red-800',
  warning: 'bg-amber-50 border-amber-300 text-amber-800',
  institution: 'bg-violet-50 border-violet-300 text-violet-800',
}
</script>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease;
}
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}
.toast-move {
  transition: transform 0.3s ease;
}
</style>
