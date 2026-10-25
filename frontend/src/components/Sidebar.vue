<script setup>
import { computed, ref } from 'vue'
import TipsPanel from './TipsPanel.vue'
import { useAppContext } from '../composables/useAppContext'

defineProps({
  t: { type: Object, required: true },
})

const app = useAppContext()
const sidebarOpen = computed(() => app.sidebarOpen)
const showView = app.showView
const activeItem = computed(() => app.currentView)
const tipsOpen = ref(false)

const navItems = [
  { key: 'home', labelKey: 'home', icon: 'home' },
  { key: 'ptmd', labelKey: 'ptmd', icon: 'ptmd' },
  { key: 'mkhp', labelKey: 'mkhp', icon: 'mkhp' },
  { key: 'templates', labelKey: 'templates', icon: 'templates' },
  { key: 'accountManagement', labelKey: 'accountManagement', icon: 'account' },
  { key: 'setting', labelKey: 'setting', icon: 'setting' },
]

function handleNav(item) {
  showView(item.key)
  tipsOpen.value = false
}
</script>

<template>
  <aside class="railm" :class="{ 'railm--open': sidebarOpen }">
    <button
      v-for="item in navItems"
      :key="item.key"
      class="railm__item"
      :class="{ 'railm__item--active': activeItem === item.key }"
      type="button"
      :aria-label="t.sideNav[item.labelKey]"
      @click="handleNav(item)"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round">
        <template v-if="item.icon === 'home'">
          <path d="M3.5 11 12 4l8.5 7v9h-17z" />
          <path d="M9.5 20v-6h5v6" />
        </template>
        <template v-else-if="item.icon === 'ptmd'">
          <rect x="3" y="4" width="18" height="16" rx="2.5" />
          <path d="M3 9h18M8 4v16" />
        </template>
        <template v-else-if="item.icon === 'mkhp'">
          <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
        </template>
        <template v-else-if="item.icon === 'templates'">
          <rect x="3" y="3" width="7" height="7" rx="2" />
          <rect x="14" y="3" width="7" height="7" rx="2" />
          <rect x="3" y="14" width="7" height="7" rx="2" />
          <rect x="14" y="14" width="7" height="7" rx="2" />
        </template>
        <template v-else-if="item.icon === 'account'">
          <circle cx="12" cy="8" r="3.6" />
          <path d="M4.5 20c1.2-3.6 4-5.4 7.5-5.4s6.3 1.8 7.5 5.4" />
        </template>
        <template v-else-if="item.icon === 'setting'">
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 3v2.4M12 18.6V21M3 12h2.4M18.6 12H21M5.6 5.6l1.7 1.7M16.7 16.7l1.7 1.7M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7" />
        </template>
      </svg>
      <span class="railm__tip">{{ t.sideNav[item.labelKey] }}</span>
    </button>

    <div class="railm__sep"></div>

    <button
      class="railm__item"
      :class="{ 'railm__item--active': tipsOpen }"
      type="button"
      :aria-label="t.sideNav.tips"
      @click="tipsOpen = !tipsOpen"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M9.6 9.2a2.6 2.6 0 1 1 3.5 2.5c-.6.2-1 .8-1 1.5v.6" />
        <path d="M12 17.2h.01" />
      </svg>
      <span class="railm__tip">{{ t.sideNav.tips }}</span>
    </button>

    <div v-if="tipsOpen" class="railm__panel">
      <TipsPanel :t="t" />
    </div>
  </aside>
</template>

<style scoped>
.railm__panel {
  position: fixed;
  top: calc(var(--topbar-height) + 12px);
  left: calc(var(--sidebar-width) + 10px);
  width: 300px;
  max-height: 70vh;
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
  box-shadow: 0 30px 60px -40px rgba(23, 20, 16, 0.55);
  z-index: 80;
}

.railm__panel :deep(*) {
  color: var(--ink-2);
}

.railm__panel :deep(h1),
.railm__panel :deep(h2),
.railm__panel :deep(h3) {
  color: var(--ink);
  font-size: 14px;
  margin: 0 0 8px;
}

@media (max-width: 767px) {
  .railm__panel {
    left: 12px;
    width: calc(100vw - 24px);
  }
}
</style>
