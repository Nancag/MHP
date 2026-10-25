<script setup>
import { ref, reactive, computed, provide, onMounted, onUnmounted } from 'vue'
import { messages } from './i18n/index.js'
import Sidebar from './components/Sidebar.vue'
import TopBar from './components/TopBar.vue'
import HeroSection from './components/HeroSection.vue'
import FeatureSection from './components/FeatureSection.vue'
import PTMDWorkbench from './views/PTMDWorkbench.vue'
import AccountManagement from './views/AccountManagement.vue'
import AuthDialog from './components/AuthPanel.vue'
import WorkspaceCenter from './views/WorkspaceCenter.vue'
import {workspaceRequest} from './api/client'
import { fetchCurrentUser, logoutUser } from './api/client'

const theme = ref('light')
const locale = ref('zh')
const sidebarOpen = ref(false)
const currentView = ref(new URLSearchParams(location.search).has('membership_order') ? 'accountManagement' : 'home')
const user = ref(null)
const authReady = ref(false)
const authOpen = ref(false)
const authError = ref('')
const authMode=ref('login')
const isNative=Boolean(window.__MHP_NATIVE__)
const templateToApply=ref(null)
const creditsRevision=ref(0)
const workbenchBusy=ref(false)
function creditsChanged(){creditsRevision.value++}
let pendingView = null
let preferencesVersion = 0

async function loadPreferences(account) {
  const version = ++preferencesVersion
  try {
    const settings = await workspaceRequest('/workspace/settings')
    if (version !== preferencesVersion || user.value !== account) return
    if (['light', 'dark'].includes(settings.preferences?.theme)) theme.value = settings.preferences.theme
    if (['zh', 'en'].includes(settings.preferences?.locale)) locale.value = settings.preferences.locale
  } catch {}
}

function clearAccountState() {
  preferencesVersion++
  user.value = null
  templateToApply.value = null
  appContext.referenceLibraryToOpen = null
  workbenchBusy.value = false
  currentView.value = 'home'
  pendingView = null
  sidebarOpen.value = false
}

function openAuth(mode='login') { authMode.value=typeof mode==='string'?mode:'login';authOpen.value = true }
function authenticated(value) {
  user.value = value
  authOpen.value = false
  authError.value = ''
  loadPreferences(user.value)
  if (pendingView) { currentView.value = pendingView; pendingView = null }
}
async function logout() {
  try {
    await logoutUser()
    clearAccountState()
    authOpen.value = true
    authError.value = ''
  } catch (error) { authError.value = error.message }
}
function unauthorized() { clearAccountState(); authOpen.value = true }
onMounted(async () => {
  window.addEventListener('mhp:unauthorized', unauthorized)
  try { user.value = (await fetchCurrentUser()).user
    await loadPreferences(user.value)
  } catch (error) {
    if (error.status !== 401) authError.value = error.message
    authOpen.value = true
  } finally { authReady.value = true }
})
onUnmounted(() => { preferencesVersion++; window.removeEventListener('mhp:unauthorized', unauthorized) })

const t = computed(() => messages[locale.value])

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

function toggleLocale() {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function closeSidebar() {
  sidebarOpen.value = false
}

function showView(view) {
  if (['accountManagement','setting','mkhp','templates'].includes(view) && !user.value) { pendingView = view; openAuth(); closeSidebar(); return }
  if (view === 'ptmd' && !user.value) { pendingView = view; openAuth(); closeSidebar(); return }
  currentView.value = view
  closeSidebar()
}

const appContext = reactive({
  theme,
  locale,
  sidebarOpen,
  currentView,
  toggleTheme,
  toggleLocale,
  toggleSidebar,
  closeSidebar,
  showView,
  user,
  openAuth,
  logout,
  templateToApply,
  referenceLibraryToOpen: null,
  isNative,
  creditsRevision,
  creditsChanged,
  workbenchBusy,
})

provide('appContext', appContext)
</script>

<template>
  <div class="app-shell" :data-theme="theme" :class="{ 'sidebar-open': sidebarOpen }">
    <TopBar :t="t" />

    <div class="shell-body">
      <Sidebar :t="t" />
      <div v-if="sidebarOpen" class="rail-overlay" @click="closeSidebar" aria-hidden="true"></div>

      <main class="shell-main">
        <PTMDWorkbench
          v-if="authReady && user && currentView === 'ptmd'"
          :t="t"
          @go-home="showView('home')"
        />
        <template v-else>
          <WorkspaceCenter
            v-if="['setting','mkhp','templates'].includes(currentView)"
            :key="currentView"
            :initial-tab="currentView==='mkhp'?'research':currentView==='templates'?'templates':'settings'"
          />
          <AccountManagement
            v-else-if="currentView === 'accountManagement'"
            :t="t"
            :user="user"
            @go-home="showView('home')"
          />
          <div v-else class="page">
            <HeroSection :t="t" />
            <FeatureSection :t="t" />
          </div>
        </template>
      </main>
    </div>

    <p v-if="authError" class="auth-app-error" role="alert">{{ authError }}</p>
    <AuthDialog v-if="authReady && authOpen && !user" :t="t" :initial-mode="authMode" :is-native="isNative" @authenticated="authenticated" @close="authOpen = false; pendingView = null" />
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  background: var(--bg-root);
  color: var(--text-primary);
  transition: background var(--transition-smooth), color var(--transition-smooth);
}

.auth-app-error {
  position: fixed;
  bottom: 20px;
  left: 20px;
  z-index: 250;
  background: var(--ink);
  color: var(--paper);
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 13px;
  box-shadow: 0 18px 40px -26px rgba(0, 0, 0, 0.6);
}
</style>
