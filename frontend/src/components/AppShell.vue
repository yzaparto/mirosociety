<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar (hidden on simulation view) -->
    <nav
      v-if="!hideShell"
      class="h-12 border-b border-slate-800/60 flex items-center px-5 gap-4 shrink-0 bg-slate-950 sticky top-0 z-40"
    >
      <router-link to="/" class="flex items-center gap-2 group">
        <div class="w-6 h-6 rounded-md bg-emerald-600 flex items-center justify-center text-white text-[10px] font-black group-hover:bg-emerald-500 transition-colors">M</div>
        <span class="font-semibold text-sm text-slate-200 group-hover:text-white transition-colors">MiroSociety</span>
      </router-link>

      <div class="flex-1"></div>

      <!-- Active simulation indicator -->
      <router-link
        v-if="activeSim"
        :to="`/simulation/${activeSim.id}`"
        class="flex items-center gap-2 text-[11px] text-emerald-400 hover:text-emerald-300 bg-emerald-950/40 border border-emerald-800/30 rounded-lg px-3 py-1.5 transition-colors"
      >
        <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
        {{ activeSim.name || 'Simulation running' }}
      </router-link>

      <router-link
        to="/gallery"
        :class="[
          'text-sm px-3 py-1.5 rounded-md transition-colors',
          isGallery ? 'text-white bg-slate-800' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        ]"
      >
        Gallery
      </router-link>

      <a
        href="https://github.com/yzaparto/mirosociety"
        target="_blank"
        rel="noopener noreferrer"
        class="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white px-3 py-1.5 rounded-md hover:bg-slate-800/50 transition-colors"
      >
        <svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        <span>Star</span>
      </a>
    </nav>

    <!-- Page content -->
    <main :class="hideShell ? '' : 'flex-1'">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const hideShell = computed(() => route.meta?.hideShell === true)
const isGallery = computed(() => route.name === 'gallery')

const activeSim = computed(() => {
  try {
    const raw = localStorage.getItem('mirosociety_active_sim')
    if (!raw) return null
    const data = JSON.parse(raw)
    if (route.name === 'simulation' && route.params.id === data.id) return null
    return data
  } catch { return null }
})
</script>
