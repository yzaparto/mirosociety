<template>
  <div class="border-t border-gray-200 h-10 flex items-center px-5 gap-4 shrink-0 bg-white/80 backdrop-blur-sm">
    <MetricBar
      v-for="m in SOCIAL_METRICS"
      :key="m.key"
      :metric-key="m.key"
      :value="metrics[m.key]"
      :prev-value="prevMetrics[m.key]"
      :label="m.label"
    />
    <template v-if="showMarket">
      <div class="w-px h-4 bg-gray-200"></div>
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
