<script setup>
import ThemeSwitcher from '../ThemeSwitcher.vue'
import LanguageSwitcher from '../LanguageSwitcher.vue'
import { useAppContext } from '../../composables/useAppContext'
const app = useAppContext()

defineProps({
  t: { type: Object, required: true },
})

defineEmits(['go-home'])

const taskState = { label: 'idle', icon: true }
</script>

<template>
  <header class="wb-toolbar">
    <div class="wb-toolbar__left">
      <button class="wb-back" type="button" @click="$emit('go-home')">
        <svg
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M19 12 H5" />
          <path d="M12 19 l-7 -7 l7 -7" />
        </svg>
        <span>{{ t.ptmd.backHome }}</span>
      </button>

      <div class="wb-brand">
        <span class="wb-brand__logo">PTMD</span>
        <span class="wb-brand__divider"></span>
        <span class="wb-brand__sub">{{ t.ptmd.subtitle }}</span>
      </div>
    </div>

    <div class="wb-toolbar__right">
      <div class="wb-task" :title="t.ptmd.taskIdle">
        <span class="wb-task__dot" :class="{ 'wb-task__dot--idle': taskState.label === 'idle' }"></span>
        <span class="wb-task__text">{{ t.ptmd.taskIdle }}</span>
      </div>
      <div class="wb-toolbar__switchers">
        <ThemeSwitcher />
        <LanguageSwitcher />
      </div>
      <div class="wb-user">
        <span class="wb-user__avatar">
          <svg
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 12 a4 4 0 1 0 0 -8 a4 4 0 0 0 0 8 Z" />
            <path d="M5 20 a7 7 0 0 1 14 0" />
          </svg>
        </span>
        <button type="button" class="wb-user__name" @click="app.openAuth">{{ app.user?.username || t.auth.loginSignup }}</button>
        <button v-if="app.user" type="button" @click="app.logout">{{ t.auth.logout }}</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.wb-toolbar {
  position: relative;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--wb-toolbar-h);
  padding: 0 20px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-dim);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.wb-toolbar__left,
.wb-toolbar__right {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.wb-back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-smooth), transform var(--transition-fast);
}

.wb-back:hover {
  color: var(--neon-blue);
  border-color: var(--neon-blue);
  box-shadow: 0 0 12px var(--glow-blue);
  transform: translateY(-1px);
}

.wb-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.wb-brand__logo {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 2px;
  background: var(--logo-grad);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: var(--logo-glow);
}

.wb-brand__divider {
  width: 1px;
  height: 18px;
  background: var(--border-dim);
}

.wb-brand__sub {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wb-task {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
}

.wb-task__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-blue);
  box-shadow: 0 0 8px var(--glow-blue);
  animation: glowPulse 2.6s ease-in-out infinite;
}

.wb-task__dot--idle {
  animation: none;
  background: var(--text-secondary);
  box-shadow: none;
}

.wb-task__text {
  font-size: 12px;
  color: var(--text-secondary);
}

.wb-toolbar__switchers {
  display: flex;
  gap: 8px;
}

.wb-user {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 12px 6px 6px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
}

.wb-user__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--grad-active);
  color: #ffffff;
}

.wb-user__name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .wb-brand__sub,
  .wb-user__name {
    display: none;
  }
}

@media (max-width: 639px) {
  .wb-back span {
    display: none;
  }
  .wb-brand__divider {
    display: none;
  }
  .wb-task {
    display: none;
  }
  .wb-toolbar {
    padding: 0 12px;
  }
}
</style>
