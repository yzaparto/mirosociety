<template>
  <div
    @click="$emit('click')"
    :class="[
      'rounded-full flex items-center justify-center font-bold border cursor-pointer transition-all',
      moodBgClass(agent.emotional_state),
      selected ? 'ring-2 ring-emerald-400 ring-offset-1 ring-offset-[#fafafa]' : '',
      sizeClasses,
    ]"
    :title="agent.name"
  >
    {{ agent.name?.charAt(0) }}
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { moodBgClass } from '../utils/mood'

const props = defineProps({
  agent: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  size: { type: String, default: 'md' },
})

defineEmits(['click'])

const sizeClasses = computed(() => ({
  sm: 'w-5 h-5 text-[8px]',
  md: 'w-7 h-7 text-[10px]',
  lg: 'w-9 h-9 text-xs',
}[props.size] || 'w-7 h-7 text-[10px]'))
</script>
