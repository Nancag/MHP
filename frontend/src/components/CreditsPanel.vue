<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchAccount, claimDailyCheckin } from '../api/client'
import { membershipMessages } from '../i18n/membership'
import { useAppContext } from '../composables/useAppContext'
const app=useAppContext()

const props = defineProps({ t: { type: Object, required: true } })
const m = computed(() => membershipMessages[props.t.account.breadcrumb === 'Account' ? 'en' : 'zh'])
const state = ref(null), loading = ref(false), busy = ref(false), message = ref(''), error = ref('')
const failure = e => e.code === 'NETWORK' ? m.value.network : (props.t.account.breadcrumb === 'Account' ? m.value.error : e.message)

async function load() {
  if (loading.value || busy.value) return
  loading.value = true
  error.value = ''
  try { state.value = await fetchAccount() }
  catch (e) { error.value = failure(e) }
  finally { loading.value = false }
}

async function checkin() {
  if (busy.value || loading.value || state.value?.checked_in_today) return
  busy.value = true
  error.value = ''
  try {
    const result = await claimDailyCheckin()
    state.value = { ...state.value, ...result }
    app.creditsChanged()
    message.value = result.awarded > 0 ? m.value.awarded : m.value.checked
  } catch (e) { error.value = failure(e) }
  finally { busy.value = false }
}

onMounted(load)
</script>

<template>
  <section class="credits-panel">
    <div class="credits-heading">
      <h2>{{ m.title }}</h2>
      <button type="button" :disabled="loading || busy" @click="load">{{ loading ? m.loading : m.refresh }}</button>
    </div>
    <p v-if="error" class="credits-error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="state">
      <div class="credit-summary"><strong class="credit-total">{{ state.available }}</strong><span>{{ m.available }}</span></div>
      <button class="checkin-button" type="button" :disabled="loading || busy || state.checked_in_today" @click="checkin">{{ state.checked_in_today ? m.checked : m.checkin }}</button>
      <p v-if="state.reserved">{{ m.reserved }}: {{ state.reserved }}</p>
      <p>{{ m.rules }}</p>
      <p>{{ m.charging }}</p>
    </template>
  </section>
</template>

<style scoped>
.credits-panel{color:var(--text-secondary);font-size:13px;line-height:1.65;min-width:0}.credits-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.credits-heading h2{font-size:19px;color:var(--text-primary);margin:0}.credits-panel button{border:1px solid var(--border-dim);border-radius:10px;background:var(--bg-glass);color:var(--text-primary);padding:9px 13px;cursor:pointer}.credits-panel button:disabled{opacity:.5;cursor:not-allowed}.credit-summary{display:flex;align-items:baseline;flex-wrap:wrap;gap:12px;margin:22px 0}.credit-total{font-size:38px;color:var(--neon-blue)}.credits-panel .checkin-button{background:var(--grad-btn);color:white}.credits-error{color:#e85c5c}
</style>
