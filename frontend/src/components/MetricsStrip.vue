<template>
  <div class="border-t border-slate-800/40 h-9 flex items-center px-4 gap-4 shrink-0 bg-slate-900/30">
    <MetricBar
      v-for="m in SOCIAL_METRICS"
      :key="m.key"
      :metric-key="m.key"
      :value="metrics[m.key]"
      :prev-value="prevMetrics[m.key]"
      :label="m.label"
    />
    <template v-if="showMarket">
      <div class="w-px h-4 bg-slate-700/60"></div>
      <MetricBar
        v-for="m in MARKET_METRICS"
        :key="m.key"
        :metric-key="m.key"
        :value="metrics[m.key]"
        :prev-value="prevMetrics[m.key]"
        :label="m.label"
      />
    </template>
    <div class="flex-1"></div>
    <slot name="right" />
  </div>
</template>

<script setup>
import MetricBar from './MetricBar.vue'
import { SOCIAL_METRICS, MARKET_METRICS } from '../utils/metrics'

defineProps({
  metrics: { type: Object, default: () => ({}) },
  prevMetrics: { type: Object, default: () => ({}) },
  showMarket: { type: Boolean, default: false },
})
</script>
