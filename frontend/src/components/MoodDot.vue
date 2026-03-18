<template>
  <div :class="[moodDotClass(state), sizeClasses, 'rounded-full shrink-0']"></div>
</template>

<script setup>
import { computed } from 'vue'
import { moodDotClass } from '../utils/mood'

const props = defineProps({
  state: String,
  size: { type: String, default: 'sm' },
})

const sizeClasses = computed(() => ({
  xs: 'w-1.5 h-1.5',
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
}[props.size] || 'w-2 h-2'))
</script>
