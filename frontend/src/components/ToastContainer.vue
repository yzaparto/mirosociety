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
  info: 'bg-emerald-950 border-emerald-800 text-emerald-200',
  danger: 'bg-red-950 border-red-800 text-red-200',
  warning: 'bg-amber-950 border-amber-800 text-amber-200',
  institution: 'bg-violet-950 border-violet-800 text-violet-200',
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
