<template>
  <div
    :class="[
      'bg-slate-900/60 border rounded-lg p-4 border-l-4 transition-colors hover:bg-slate-900/80',
      typeBorder,
    ]"
  >
    <div class="flex items-center gap-2 mb-1.5">
      <span :class="['text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded', typeBadge]">
        {{ insight.type }}
      </span>
      <h3 class="font-medium text-sm">{{ insight.title }}</h3>
    </div>
    <p class="text-sm text-slate-400 leading-relaxed">{{ insight.description }}</p>
    <div v-if="insight.evidence" class="mt-2.5 flex flex-wrap gap-1.5">
      <span
        v-for="agent in (insight.evidence.agents || []).slice(0, 4)"
        :key="agent"
        class="text-[10px] bg-slate-800/80 text-slate-400 px-1.5 py-0.5 rounded"
      >
        {{ agent }}
      </span>
      <span
        v-for="day in (insight.evidence.days || []).slice(0, 4)"
        :key="day"
        class="text-[10px] bg-slate-800/80 text-slate-400 px-1.5 py-0.5 rounded"
      >
        Day {{ day }}
      </span>
      <span
        v-for="action in (insight.evidence.actions || []).slice(0, 3)"
        :key="action"
        class="text-[10px] bg-slate-800/80 text-slate-400 px-1.5 py-0.5 rounded"
      >
        {{ action }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  insight: { type: Object, required: true },
})

const typeBorder = computed(() => ({
  opportunity: 'border-l-blue-500 border-slate-800/40',
  risk: 'border-l-red-500 border-slate-800/40',
  finding: 'border-l-amber-500 border-slate-800/40',
}[props.insight.type] || 'border-l-amber-500 border-slate-800/40'))

const typeBadge = computed(() => ({
  opportunity: 'bg-blue-500/20 text-blue-400',
  risk: 'bg-red-500/20 text-red-400',
  finding: 'bg-amber-500/20 text-amber-400',
}[props.insight.type] || 'bg-amber-500/20 text-amber-400'))
</script>
