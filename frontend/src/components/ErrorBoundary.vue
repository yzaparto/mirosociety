<template>
  <div v-if="error" class="min-h-[50vh] flex items-center justify-center px-6">
    <div class="text-center max-w-md">
      <div class="w-14 h-14 rounded-2xl bg-red-950/40 border border-red-800/40 flex items-center justify-center text-2xl mx-auto mb-4">!</div>
      <h2 class="text-lg font-semibold mb-2 text-slate-200">Something went wrong</h2>
      <p class="text-sm text-slate-500 mb-4">{{ error.message || 'An unexpected error occurred.' }}</p>
      <div class="flex gap-3 justify-center">
        <button @click="retry" class="btn-secondary text-sm">Try Again</button>
        <router-link to="/" class="btn-secondary text-sm">Go Home</router-link>
      </div>
    </div>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'

const error = ref(null)

onErrorCaptured((err) => {
  error.value = err
  console.error('ErrorBoundary caught:', err)
  return false
})

function retry() {
  error.value = null
}
</script>
