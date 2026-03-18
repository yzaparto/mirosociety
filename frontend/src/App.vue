<template>
  <AppShell>
    <ErrorBoundary>
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </ErrorBoundary>
  </AppShell>
</template>

<script setup>
import AppShell from './components/AppShell.vue'
import ErrorBoundary from './components/ErrorBoundary.vue'
</script>

<style>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}
</style>
