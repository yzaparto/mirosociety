<template>
  <div class="min-h-screen py-12">
    <div class="max-w-5xl mx-auto px-6">
      <div class="flex items-center justify-between mb-8">
        <div>
          <h1 class="text-3xl font-bold">Gallery</h1>
          <p class="text-sm text-slate-500 mt-1">Public simulations from the community</p>
        </div>
      </div>

      <!-- Filters row -->
      <div class="flex flex-wrap items-center gap-3 mb-6">
        <!-- Category tabs -->
        <div class="flex gap-1 bg-slate-800/40 rounded-lg p-0.5">
          <button
            v-for="cat in categories"
            :key="cat.id"
            @click="category = cat.id; loadGallery()"
            :class="[
              'text-xs px-3 py-1.5 rounded-md font-medium transition-colors',
              category === cat.id ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'
            ]"
          >
            {{ cat.label }}
          </button>
        </div>

        <!-- Sort -->
        <div class="flex gap-1 bg-slate-800/40 rounded-lg p-0.5">
          <button
            v-for="s in sortOptions"
            :key="s.id"
            @click="sort = s.id; loadGallery()"
            :class="[
              'text-xs px-3 py-1.5 rounded-md font-medium transition-colors capitalize',
              sort === s.id ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'
            ]"
          >
            {{ s.label }}
          </button>
        </div>

        <div class="flex-1"></div>

        <!-- Search -->
        <div class="relative">
          <input
            v-model="search"
            @input="debouncedSearch"
            placeholder="Search simulations..."
            class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 pl-8 text-sm text-slate-200 outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30 placeholder-slate-500 w-56 transition-colors"
          />
          <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div v-for="i in 4" :key="i" class="h-32 bg-slate-900/40 rounded-lg animate-pulse"></div>
      </div>

      <!-- Empty state -->
      <div v-else-if="simulations.length === 0" class="text-center py-20">
        <div class="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mx-auto mb-4">
          <svg class="w-7 h-7 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
        </div>
        <p class="text-slate-500 mb-2">No simulations found.</p>
        <router-link to="/" class="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">Run your first simulation →</router-link>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <TransitionGroup name="list">
          <router-link
            v-for="sim in simulations"
            :key="sim.id"
            :to="`/report/${sim.id}`"
            class="card card-hover group"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="font-semibold text-slate-100 group-hover:text-white transition-colors">{{ sim.world_name || 'Unnamed' }}</h3>
              <span v-if="sim.verdict" :class="[
                'text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded shrink-0',
                sim.verdict === 'go' ? 'bg-emerald-500/20 text-emerald-400' :
                sim.verdict === 'rethink' ? 'bg-red-500/20 text-red-400' :
                'bg-amber-500/20 text-amber-400'
              ]">
                {{ sim.verdict }}
              </span>
            </div>
            <p class="text-sm text-slate-400 line-clamp-2 mb-3">{{ sim.rules_text }}</p>

            <!-- Mini metric bars -->
            <div v-if="sim.final_metrics" class="flex gap-1 mb-2">
              <div v-for="mk in ['stability', 'trust', 'conflict', 'freedom', 'prosperity']" :key="mk"
                class="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden" :title="mk">
                <div
                  :class="['h-full rounded-full', miniBarColor(mk, sim.final_metrics[mk])]"
                  :style="{ width: ((sim.final_metrics[mk] ?? 0.5) * 100) + '%' }"
                ></div>
              </div>
            </div>

            <div class="flex gap-3 text-xs text-slate-500">
              <span>{{ sim.agent_count }} citizens</span>
              <span>{{ sim.view_count || 0 }} views</span>
              <span>{{ sim.fork_count || 0 }} forks</span>
              <span v-if="sim.created_at" class="ml-auto">{{ timeAgo(sim.created_at) }}</span>
            </div>
          </router-link>
        </TransitionGroup>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { timeAgo } from '../utils/format'

const simulations = ref([])
const sort = ref('recent')
const category = ref('all')
const search = ref('')
const loading = ref(true)

const categories = [
  { id: 'all', label: 'All' },
  { id: 'social', label: 'Social' },
  { id: 'market', label: 'Market' },
]

const sortOptions = [
  { id: 'recent', label: 'Recent' },
  { id: 'views', label: 'Views' },
  { id: 'forks', label: 'Forks' },
]

let searchTimeout = null

function debouncedSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => loadGallery(), 300)
}

function miniBarColor(key, value) {
  const v = value ?? 0.5
  if (key === 'conflict') return v >= 0.6 ? 'bg-red-400' : v <= 0.3 ? 'bg-emerald-400' : 'bg-amber-400'
  return v >= 0.6 ? 'bg-emerald-400' : v <= 0.3 ? 'bg-red-400' : 'bg-amber-400'
}

async function loadGallery() {
  loading.value = true
  try {
    const data = await api.getGallery(sort.value)
    let sims = data.simulations || []

    if (search.value.trim()) {
      const q = search.value.toLowerCase()
      sims = sims.filter(s =>
        (s.world_name || '').toLowerCase().includes(q) ||
        (s.rules_text || '').toLowerCase().includes(q)
      )
    }

    simulations.value = sims
  } catch (e) {
    console.error('Failed to load gallery:', e)
  }
  loading.value = false
}

onMounted(loadGallery)
</script>
