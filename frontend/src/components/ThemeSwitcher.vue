<script setup>
import { toRefs } from 'vue'
import { useAppContext } from '../composables/useAppContext'

const context = useAppContext()
const { toggleTheme } = context
const { theme } = toRefs(context)
</script>

<template>
  <button
    class="iconbtn"
    type="button"
    :title="context.locale === 'en' ? (theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme') : (theme === 'dark' ? '切到纸墨（浅色）' : '切到暗房（深色）')"
    :aria-label="context.locale === 'en' ? 'Toggle theme' : '切换主题'"
    @click="toggleTheme"
  >
    <svg v-if="theme === 'dark'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M19.1 4.9l-1.7 1.7M6.6 17.4l-1.7 1.7" />
    </svg>
    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
    </svg>
  </button>
</template>

<style scoped>
.iconbtn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-full);
  border: 1px solid var(--line);
  color: var(--ink-2);
  background: transparent;
  transition: color var(--transition-fast), border-color var(--transition-fast),
    background var(--transition-fast);
}
.iconbtn:hover {
  color: var(--ink);
  border-color: var(--ink);
  background: rgba(23, 20, 16, 0.04);
}
[data-theme='dark'] .iconbtn:hover { background: rgba(242, 236, 226, 0.06); }
.iconbtn svg { width: 17px; height: 17px; }
</style>
