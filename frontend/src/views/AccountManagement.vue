<script setup>
import { ref } from 'vue'
import CreditsPanel from '../components/CreditsPanel.vue'
import { useAppContext } from '../composables/useAppContext'

defineProps({
  t: { type: Object, required: true },
  user: { type: Object, default: null },
})

const emit = defineEmits(['go-home'])

const app = useAppContext()


const copiedField = ref('')
const showSwitchDialog = ref(false)

function copyToClipboard(text, field) {
  if (!text) return
  try {
    navigator.clipboard.writeText(text).then(() => {
      copiedField.value = field
      setTimeout(() => { copiedField.value = '' }, 2000)
    })
  } catch {
    /* clipboard not available */
  }
}

function handleLogout() {
  app.logout()
}

function handleSwitchAccount() {
  showSwitchDialog.value = true
}

function confirmSwitch() {
  showSwitchDialog.value = false
  app.logout()
}

function cancelSwitch() {
  showSwitchDialog.value = false
}
</script>

<template>
  <div class="am-page">
    <div class="am-container">
      <!-- 账号信息区 -->
      <section class="am-section am-section--account">
        <div class="am-breadcrumb">
          <span>{{ t.account.breadcrumb }}</span>
          <svg class="am-breadcrumb__arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </div>

        <div class="am-account-row">
          <div class="am-account-left">
            <span class="am-avatar">
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 12 a4 4 0 1 0 0 -8 a4 4 0 0 0 0 8 Z" />
                <path d="M5 20 a7 7 0 0 1 14 0" />
              </svg>
            </span>
            <div class="am-account-info">
              <div class="am-username-row">
                <span class="am-username">{{ user?.username || '—' }}</span>
                <button class="am-copy-btn" type="button" @click="copyToClipboard(user?.username, 'username')">
                  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="11" height="11" rx="2" />
                    <path d="M5 15 V5 a2 2 0 0 1 2 -2 h10" />
                  </svg>
                  <span v-if="copiedField === 'username'" class="am-copied">{{ t.account.copied }}</span>
                </button>
              </div>
              <div class="am-id-row">
                <span class="am-id-label">{{ t.account.accountId }}：</span>
                <span class="am-id-value">{{ user?.user_id || '—' }}</span>
                <button class="am-copy-btn" type="button" @click="copyToClipboard(user?.user_id, 'userid')">
                  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="11" height="11" rx="2" />
                    <path d="M5 15 V5 a2 2 0 0 1 2 -2 h10" />
                  </svg>
                  <span v-if="copiedField === 'userid'" class="am-copied">{{ t.account.copied }}</span>
                </button>
              </div>
              <div class="am-tags">
                <span class="am-tag am-tag--main">{{ t.account.tagMain }}</span>
                <span class="am-tag am-tag--verified">{{ t.account.tagVerified }}</span>
              </div>
            </div>
          </div>

          <button class="am-logout-btn" type="button" @click="handleLogout">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21 H5 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 h4" />
              <path d="M16 17 l5 -5 l-5 -5" />
              <path d="M21 12 H9" />
            </svg>
            <span>{{ t.account.logout }}</span>
          </button>
        </div>
      </section>

      <section class="am-section"><CreditsPanel :t="t" /></section>

      <!-- 权限与安全 -->
      <section class="am-section">
        <div class="am-section-header">
          <svg class="am-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11 V7 a5 5 0 0 1 10 0 v4" />
          </svg>
          <span class="am-section-title">{{ t.account.permissionSecurity }}</span>
        </div>
        <div class="am-security-list">
          <div class="am-security-item">
            <svg class="am-security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="M2 7 h20 M6 4 v-2 M18 4 v-2" />
            </svg>
            <span class="am-security-label">{{ t.account.boundEmail }}</span>
            <span class="am-security-value">{{ user?.email || '—' }}</span>
          </div>
          <div class="am-security-item">
            <svg class="am-security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M7 8 a5 5 0 0 1 10 0" />
              <path d="M7 8 v4 a5 5 0 0 0 10 0 V8" />
              <path d="M12 17 v4 M9 21 h6" />
            </svg>
            <span class="am-security-label">{{ t.account.switchAccount }}</span>
            <button class="am-link-btn" type="button" @click="handleSwitchAccount">{{ t.account.switchBtn }}</button>
          </div>
          <div class="am-security-item">
            <svg class="am-security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21 H5 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 h4" />
              <path d="M16 17 l5 -5 l-5 -5" />
              <path d="M21 12 H9" />
            </svg>
            <span class="am-security-label">{{ t.account.logoutAction }}</span>
            <button class="am-link-btn am-link-btn--danger" type="button" @click="handleLogout">{{ t.account.logout }}</button>
          </div>
        </div>
      </section>

    </div>

    <Transition name="am-dialog">
      <div v-if="showSwitchDialog" class="am-dialog-overlay" @click.self="cancelSwitch">
        <div class="am-dialog" role="dialog" aria-modal="true">
          <h3 class="am-dialog__title">{{ t.account.switchDialogTitle }}</h3>
          <p class="am-dialog__desc">{{ t.account.switchDialogDesc }}</p>
          <div class="am-dialog__actions">
            <button class="am-dialog__btn am-dialog__btn--cancel" type="button" @click="cancelSwitch">{{ t.account.switchDialogCancel }}</button>
            <button class="am-dialog__btn am-dialog__btn--confirm" type="button" @click="confirmSwitch">{{ t.account.switchDialogConfirm }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.am-security-list{display:grid;gap:16px}.am-security-item{display:flex;align-items:center;gap:10px;min-width:0;flex-wrap:wrap}.am-security-icon{width:22px;height:22px;flex:none;color:var(--text-secondary)}.am-security-label{font-size:14px;color:var(--text-secondary)}.am-security-value{margin-left:auto;max-width:100%;overflow-wrap:anywhere;color:var(--text-primary);font-size:13px}.am-link-btn{margin-left:auto;border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-glass);color:var(--text-primary);padding:7px 12px}.am-link-btn--danger{color:#df5d5d}.am-id-row{flex-wrap:wrap}.am-id-value{min-width:0;overflow-wrap:anywhere;word-break:break-all}
.am-page {
  position: relative;
  min-height: 100vh;
  padding: calc(var(--topbar-height, 64px) + 32px) 32px 48px;
  display: flex;
  justify-content: center;
}

.am-container {
  width: 100%;
  max-width: 720px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.am-section {
  padding: 24px 28px;
  border-radius: 16px;
  background: var(--bg-card-strong, var(--bg-glass));
  border: 1px solid var(--border-dim);
  box-shadow: var(--shadow-card, none);
}

.am-section--account {
  padding-top: 20px;
}

.am-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.am-breadcrumb__arrow {
  width: 16px;
  height: 16px;
}

.am-account-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.am-account-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.am-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  flex: none;
  border-radius: 50%;
  background: var(--grad-active, linear-gradient(135deg, #3b82f6, #8b5cf6));
  color: #ffffff;
}

.am-avatar .icon {
  width: 28px;
  height: 28px;
}

.am-account-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.am-username-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.am-username {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.am-id-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.am-id-label {
  color: var(--text-secondary);
}

.am-id-value {
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
}

.am-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.am-copy-btn:hover {
  color: var(--neon-blue, #3b82f6);
  background: var(--bg-glass);
}

.am-copy-btn .icon {
  width: 15px;
  height: 15px;
}

.am-copied {
  font-size: 11px;
  color: var(--neon-blue, #3b82f6);
}

.am-tags {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.am-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.am-tag--main {
  background: rgba(59, 130, 246, 0.12);
  color: var(--neon-blue, #3b82f6);
}

.am-tag--verified {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.am-logout-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  flex: none;
  border-radius: var(--radius-full, 999px);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast);
}

.am-logout-btn:hover {
  border-color: #ef4444;
  color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.3);
}

.am-logout-btn .icon {
  width: 18px;
  height: 18px;
}

.am-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.am-section-icon {
  width: 20px;
  height: 20px;
  color: var(--text-primary);
}

.am-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.am-section-arrow {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
}

.am-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-dim);
  margin-bottom: 16px;
}

.am-tab {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.am-tab:hover {
  color: var(--text-primary);
}

.am-tab--active {
  color: var(--neon-blue, #3b82f6);
  border-bottom-color: var(--neon-blue, #3b82f6);
}

.am-tab-content {
  padding: 8px 0;
}

.am-tab-desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.am-billing {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.am-security-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.am-security-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-dim);
}

.am-security-item:last-child {
  border-bottom: none;
}

.am-security-icon {
  width: 20px;
  height: 20px;
  flex: none;
  color: var(--text-secondary);
}

.am-security-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  min-width: 100px;
}

.am-security-value {
  font-size: 14px;
  color: var(--text-secondary);
  margin-left: auto;
  font-family: 'Courier New', monospace;
}

.am-link-btn {
  margin-left: auto;
  padding: 4px 14px;
  border-radius: var(--radius-full, 999px);
  border: 1px solid var(--border-dim);
  background: transparent;
  color: var(--neon-blue, #3b82f6);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast),
    color var(--transition-fast);
}

.am-link-btn:hover {
  border-color: var(--neon-blue, #3b82f6);
  background: rgba(59, 130, 246, 0.08);
}

.am-link-btn--danger {
  color: #ef4444;
}

.am-link-btn--danger:hover {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.am-billing-text {
  color: var(--text-secondary);
}

.am-billing-status {
  color: var(--text-tertiary, var(--text-secondary));
  font-size: 12px;
}

.am-billing-links {
  gap: 24px;
  margin-top: 4px;
}

.am-section--stats {
  padding: 20px 28px;
}

.am-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.am-stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 12px;
  border-radius: 12px;
  background: var(--bg-glass);
  border: 1px solid var(--border-dim);
}

.am-stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #ff6a00;
  line-height: 1;
}

.am-stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}

@media (max-width: 767px) {
  .am-page {
    padding: calc(var(--topbar-height, 64px) + 20px) 16px 32px;
  }

  .am-section {
    padding: 20px 18px;
  }

  .am-account-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .am-stats {
    grid-template-columns: 1fr;
  }
}

.am-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.am-dialog {
  width: min(400px, 90vw);
  padding: 28px 24px 20px;
  border-radius: 16px;
  background: var(--bg-card-strong, #1a1a2e);
  border: 1px solid var(--border-glow, var(--border-dim));
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.am-dialog__title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.am-dialog__desc {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.am-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.am-dialog__btn {
  padding: 8px 20px;
  border-radius: var(--radius-full, 999px);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast),
    color var(--transition-fast);
}

.am-dialog__btn--cancel {
  border: 1px solid var(--border-dim);
  background: transparent;
  color: var(--text-secondary);
}

.am-dialog__btn--cancel:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
}

.am-dialog__btn--confirm {
  border: none;
  background: var(--grad-active, linear-gradient(135deg, #3b82f6, #8b5cf6));
  color: #ffffff;
}

.am-dialog__btn--confirm:hover {
  filter: brightness(1.1);
}

.am-dialog-enter-active,
.am-dialog-leave-active {
  transition: opacity var(--transition-fast, 0.2s);
}

.am-dialog-enter-from,
.am-dialog-leave-to {
  opacity: 0;
}
</style>
