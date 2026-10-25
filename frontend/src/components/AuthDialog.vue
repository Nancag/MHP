<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { fetchAuthConfig, sendEmailCode, verifyEmailCode } from '../api/client'

const props = defineProps({ t: { type: Object, required: true }, required: Boolean })
const emit = defineEmits(['authenticated', 'close'])
const email = ref('')
const username = ref('')
const code = ref('')
const remember = ref(false)
const challenge = ref('')
const busy = ref(false)
const cooldown = ref(0)
const error = ref('')
const notice = ref('')
const enabled = ref(false)
const needsUsername = ref(false)
const panel = ref(null)
let timer
const a = computed(() => props.t.auth)
const usernameValid = computed(() => !!username.value.trim() && Array.from(username.value.trim()).length <= 20)

onMounted(async () => {
  panel.value?.querySelector('input')?.focus()
  timer = setInterval(() => { if (cooldown.value > 0) cooldown.value-- }, 1000)
  try {
    const config = await fetchAuthConfig()
    enabled.value = config.email_enabled
  } catch { error.value = a.value.unavailable }
})
onUnmounted(() => clearInterval(timer))

function resetChallenge() { challenge.value = ''; code.value = ''; notice.value = ''; needsUsername.value = false; username.value = '' }
async function send() {
  if (busy.value || cooldown.value) return
  error.value = ''; busy.value = true
  try {
    const response = await sendEmailCode(email.value.trim())
    challenge.value = response.challenge_id
    cooldown.value = response.retry_after
    notice.value = a.value.codeSent
    await nextTick()
    panel.value?.querySelector('[name="code"]')?.focus()
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
async function verify() {
  if (busy.value || !challenge.value || (needsUsername.value && !usernameValid.value)) return
  error.value = ''; busy.value = true
  try {
    const response = await verifyEmailCode({challenge_id: challenge.value, code: code.value, username: needsUsername.value ? username.value.trim() : null, remember: remember.value})
    emit('authenticated', response.user)
  } catch (e) {
    if (e.status === 409) { needsUsername.value = true; await nextTick(); panel.value?.querySelector('[name="username"]')?.focus() }
    else error.value = e.message
  } finally { busy.value = false }
}
function trapFocus(event) {
  if (event.key === 'Escape' && !props.required) emit('close')
  if (event.key !== 'Tab') return
  const elements = [...panel.value.querySelectorAll('button:not(:disabled),input:not(:disabled),a[href]')]
  const first = elements[0], last = elements.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
</script>

<template>
  <div class="auth-overlay">
    <section ref="panel" class="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title" @keydown="trapFocus">
      <button v-if="!required" class="auth-close" type="button" :aria-label="a.close" @click="emit('close')">×</button>
      <p class="auth-brand">MHP</p>
      <h2 id="auth-title">{{ a.loginSignup }}</h2>
      <p>{{ a.description }}</p>
      <div class="auth-methods"><span>{{ a.emailMethod }}</span><span aria-disabled="true">{{ a.smsDisabled }}</span></div>
      <form @submit.prevent="verify">
        <label v-if="needsUsername">{{ a.username }}<input v-model="username" name="username" required autocomplete="nickname" :placeholder="a.usernameHint" /></label>
        <small v-if="!usernameValid && username">{{ a.usernameHint }}</small>
        <label>{{ a.email }}<input v-model="email" name="email" type="email" required autocomplete="email" @input="resetChallenge" /></label>
        <div class="auth-code-row">
          <label>{{ a.code }}<input v-model="code" name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required /></label>
          <button type="button" class="btn-ghost" :disabled="busy || cooldown > 0 || !enabled || !email" @click="send">{{ cooldown ? `${cooldown}s` : a.sendCode }}</button>
        </div>
        <label class="auth-remember"><input v-model="remember" type="checkbox" />{{ a.remember }}</label>
        <p class="auth-note">{{ a.rememberHint }}</p>
        <p v-if="!enabled" class="auth-error" role="status">{{ a.unavailable }}</p>
        <p v-if="notice" class="auth-note" role="status">{{ notice }}</p>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <button type="submit" class="btn-primary auth-submit" :disabled="busy || !challenge || (needsUsername && !usernameValid) || !/^\d{6}$/.test(code)">{{ busy ? a.processing : a.verifyLogin }}</button>
      </form>
      <p class="auth-download"><a href="/download.html">{{ t.account.breadcrumb === 'Account' ? 'Download for Windows' : '下载 Windows 客户端' }}</a></p>
    </section>
  </div>
</template>

<style scoped>
.auth-overlay { position: fixed; inset: 0; z-index: 200; background: #080b16bb; backdrop-filter: blur(8px); display: grid; place-items: center; padding: 20px; overflow: auto; }
.auth-dialog { position: relative; width: min(440px, 100%); max-height: 95vh; overflow-y: auto; padding: 28px; background: var(--bg-card-strong); border: 1px solid var(--border-glow); border-radius: 20px; box-shadow: var(--shadow-card); color: var(--text-primary); }
.auth-brand { color: var(--neon-blue); font-weight: 800; letter-spacing: 3px; margin: 0; }
.auth-dialog h2 { margin: 12px 0; }
.auth-dialog p, .auth-dialog small { font-size: 13px; line-height: 1.6; }
.auth-dialog form, .auth-dialog label { display: grid; gap: 8px; }
.auth-dialog form { gap: 16px; margin-top: 20px; }
.auth-dialog label { font-size: 14px; }
.auth-dialog input:not([type=checkbox]) { min-width: 0; width: 100%; box-sizing: border-box; padding: 11px 12px; border: 1px solid var(--border-dim); background: var(--bg-glass); border-radius: 9px; color: var(--text-primary); font: inherit; }
.auth-dialog input:focus { outline: 2px solid var(--neon-blue); outline-offset: 2px; }
.auth-methods { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--neon-blue); }
.auth-methods [aria-disabled] { color: var(--text-secondary); }
.auth-code-row { display: grid; grid-template-columns: 1fr auto; align-items: end; gap: 10px; }
.auth-code-row button { padding: 10px; font-size: 13px; }
.auth-dialog .auth-remember { display: flex; align-items: center; gap: 8px; }
.auth-note { color: var(--text-secondary); margin: 0; }
.auth-error { color: #f58c8c; margin: 0; }
.auth-submit { width: 100%; justify-content: center; }
.auth-download { text-align: center; margin: 18px 0 0; }
.auth-download a { color: var(--neon-blue); }
.auth-dialog button:disabled { opacity: .5; cursor: not-allowed; }
.auth-close { position: absolute; right: 16px; top: 12px; color: var(--text-primary); font-size: 24px; }
</style>
