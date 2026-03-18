<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar (hidden on simulation view) -->
    <nav
      v-if="!hideShell"
      class="h-12 border-b border-slate-800/60 flex items-center px-5 gap-4 shrink-0 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40"
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
