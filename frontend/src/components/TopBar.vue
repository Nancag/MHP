<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import ThemeSwitcher from './ThemeSwitcher.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'
import { useAppContext } from '../composables/useAppContext'
import { fetchAccount } from '../api/client'

const props = defineProps({
  t: { type: Object, required: true },
})

const app = useAppContext()
const menuOpen = ref(false)
const credits = ref(null)

const TITLES = {
  home: 'home',
  ptmd: 'ptmd',
  mkhp: 'mkhp',
  templates: 'templates',
  accountManagement: 'accountManagement',
  setting: 'setting',
}

const pageName = computed(() => {
  const key = TITLES[app.currentView] || 'home'
  return props.t.sideNav[key] || ''
})

const english = computed(() => props.t.account.breadcrumb === 'Account')

async function loadCredits() {
  if (!app.user) { credits.value = null; return }
  try { const data = await fetchAccount(); credits.value = data.available } catch { credits.value = null }
}

onMounted(loadCredits)
watch(() => [app.user, app.currentView, app.creditsRevision], loadCredits)
</script>

<template>
  <header class="shell-top">
    <button class="railm-toggle" type="button" aria-label="menu" @click="app.toggleSidebar()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path v-if="!app.sidebarOpen" d="M4 7h16M4 12h16M4 17h16" />
        <path v-else d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>

    <button class="brand-btn" type="button" @click="app.showView('home')">
      <b>MHP</b><i>STUDIO</i>
    </button>

    <div class="page-name">{{ pageName }}</div>

    <div class="shell-right">
      <span v-if="app.workbenchBusy" class="workbench-status" role="status">{{ english ? 'Creating…' : '正在制作…' }}</span>
      <LanguageSwitcher />
      <ThemeSwitcher />

      <div v-if="app.user && credits !== null" class="credit-pill">
        {{ english ? 'Credits' : '剩余额度' }} <b>{{ credits }}</b> {{ english ? '' : '张' }}
      </div>

      <a v-if="!app.isNative" class="solid-btn download-btn" href="/download.html">
        {{ english ? 'Desktop app status' : '客户端发布状态' }}
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
             stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 4v11M7.5 11l4.5 4.5L16.5 11M5 20h14" />
        </svg>
      </a>

      <div class="user-menu">
        <button class="user-menu__trigger" type="button" @click="app.user ? (menuOpen = !menuOpen) : app.openAuth()" :aria-expanded="app.user ? menuOpen : undefined">
          <span class="user-menu__avatar">
            {{ app.user ? (app.user.username || 'M').slice(0, 1).toUpperCase() : '' }}
            <svg v-if="!app.user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="3.6" />
              <path d="M4.5 20c1.2-3.6 4-5.4 7.5-5.4s6.3 1.8 7.5 5.4" />
            </svg>
          </span>
          <span class="user-menu__name">
            {{ app.user ? app.user.username : (english ? 'Sign in' : '登录') }}
          </span>
        </button>

        <Transition name="dropdown">
          <div v-if="menuOpen" class="user-menu__dropdown">
            <button type="button" class="dropdown-item" @click="app.showView('accountManagement'); menuOpen = false">
              {{ t.sideNav.accountManagement }}
            </button>
            <button type="button" class="dropdown-item" @click="app.showView('setting'); menuOpen = false">
              {{ t.sideNav.setting }}
            </button>
            <button v-if="app.user" type="button" class="dropdown-item" @click="app.logout(); menuOpen = false">
              {{ t.auth.logout }}
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<style scoped>
.railm-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--line);
  color: var(--ink);
}
.railm-toggle svg { width: 18px; height: 18px; }

.user-menu { position: relative; }

.user-menu__trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 10px 0 4px;
  border-radius: var(--radius-full);
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.user-menu__trigger:hover { border-color: var(--ink); background: rgba(23, 20, 16, 0.04); }
[data-theme='dark'] .user-menu__trigger:hover { background: rgba(242, 236, 226, 0.06); }

.user-menu__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--ink);
  color: var(--paper);
  font-size: 11.5px;
  font-weight: 750;
}
.user-menu__avatar svg { width: 15px; height: 15px; }

.user-menu__name {
  font-size: 12.5px;
  font-weight: 650;
  white-space: nowrap;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-menu__dropdown {
  position: absolute;
  top: calc(100% + 9px);
  right: 0;
  min-width: 168px;
  padding: 5px;
  border-radius: 11px;
  background: var(--card);
  border: 1px solid var(--line);
  box-shadow: 0 26px 44px -30px rgba(23, 20, 16, 0.85);
  z-index: 70;
}

.dropdown-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 9px 11px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  transition: background var(--transition-fast), color var(--transition-fast);
}
.dropdown-item:hover { background: var(--paper-2); color: var(--ink); }

.dropdown-enter-active,
.dropdown-leave-active { transition: opacity var(--transition-fast), transform var(--transition-fast); }
.dropdown-enter-from,
.dropdown-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 767px) {
  .railm-toggle { display: inline-flex; }
  .user-menu__name { display: none; }
  .download-btn { display: none; }
}
</style>
