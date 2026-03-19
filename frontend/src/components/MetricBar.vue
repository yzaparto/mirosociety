<template>
  <div class="flex items-center gap-1.5">
    <span class="text-[9px] text-slate-500 font-medium whitespace-nowrap">{{ label }}</span>
    <div class="w-14 h-1.5 bg-gray-100 rounded-full overflow-hidden">
      <div
        :class="['h-full rounded-full transition-all duration-700', barColor]"
        :style="{ width: pct + '%' }"
      ></div>
    </div>
    <span :class="['text-[9px] font-mono tabular-nums', trendColorClass]">{{ pct.toFixed(0) }}%</span>
    <span v-if="trendArrow" :class="['text-[9px] -ml-0.5 font-bold', trendColorClass]">{{ trendArrow }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { metricBarColor, findMetricConfig } from '../utils/metrics'

const props = defineProps({
  metricKey: { type: String, required: true },
  value: { type: Number, default: 0 },
  prevValue: { type: Number, default: null },
  label: { type: String, required: true },
})

const pct = computed(() => (props.value ?? 0) * 100)

const barColor = computed(() => metricBarColor(props.metricKey, props.value))

const delta = computed(() => {
  if (props.prevValue === null) return 0
  const d = (props.value || 0) - (props.prevValue || 0)
  return Math.abs(d) < 0.005 ? 0 : (d > 0 ? 1 : -1)
})

const trendArrow = computed(() => {
  if (delta.value > 0) return '↑'
  if (delta.value < 0) return '↓'
  return ''
})

const trendColorClass = computed(() => {
  const cfg = findMetricConfig(props.metricKey)
  if (!cfg || delta.value === 0) return 'text-slate-400'
  const isGood = cfg.goodHigh ? delta.value > 0 : delta.value < 0
  return isGood ? 'text-emerald-600' : 'text-red-600'
})
</script>
