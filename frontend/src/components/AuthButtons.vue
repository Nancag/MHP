<script setup>
import iconUser from '../assets/icons/icon-user.png'
import iconDownload from '../assets/icons/icon-download.png'
import { useAppContext } from '../composables/useAppContext'
const app = useAppContext()

defineProps({
  t: { type: Object, required: true },
})
</script>

<template>
  <div class="auth-buttons">
    <button class="btn-primary" type="button" @click="app.user?app.showView('accountManagement'):app.openAuth('login')">
      <img class="btn-icon-img" :src="iconUser" alt="" />
      <span>{{ app.user ? app.user.username : (t.account.breadcrumb==='Account'?'Sign in':'登录') }}</span>
      <svg
        class="icon icon-arrow"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M5 12 h14" />
        <path d="m12 5 7 7 -7 7" />
      </svg>
    </button>

    <button v-if="!app.user" class="btn-ghost" type="button" @click="app.openAuth('register')">{{ t.account.breadcrumb==='Account'?'Register':'注册' }}</button>
    <a v-if="!app.isNative" class="btn-ghost" href="/download.html">
      <img class="btn-icon-img" :src="iconDownload" alt="" />
      <span>{{ t.auth.downloadClient }}</span>
      <svg
        class="icon icon-arrow"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M5 12 h14" />
        <path d="m12 5 7 7 -7 7" />
      </svg>
    </a>
  </div>
</template>

<style scoped>
.auth-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  justify-content: center;
}

.btn-icon-img {
  width: 20px;
  height: 20px;
  filter: drop-shadow(0 0 4px var(--glow-blue));
}

.icon-arrow {
  width: 16px;
  height: 16px;
  transition: transform var(--transition-fast);
}

.btn-primary:hover .icon-arrow {
  transform: translateX(3px);
}

.btn-ghost:hover .icon-arrow {
  transform: translateX(3px);
}
</style>
