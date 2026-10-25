<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchAccount, claimDailyCheckin, createMembershipOrder, redeemMembershipCode } from '../api/client'
import { membershipMessages } from '../i18n/membership'
import { useAppContext } from '../composables/useAppContext'
const app=useAppContext()

const props = defineProps({ t: { type: Object, required: true } })
const m = computed(() => membershipMessages[props.t.account.breadcrumb === 'Account' ? 'en' : 'zh'])
const state = ref(null), loading = ref(false), busy = ref(false), message = ref(''), error = ref(''), redeemCode = ref(''), rechargeCredits = ref(1)
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

const money = fen => new Intl.NumberFormat(props.t.account.breadcrumb === 'Account' ? 'en-US' : 'zh-CN', {style:'currency',currency:'CNY',minimumFractionDigits:0}).format(fen / 100)
async function buy() {
  if (busy.value || !state.value?.payment_enabled) return
  const credits = Number(rechargeCredits.value)
  if (!Number.isInteger(credits) || credits < state.value.minimum_recharge || credits > state.value.maximum_recharge) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const order = await createMembershipOrder({credits, request_id:crypto.randomUUID()})
    if (order.checkout_url) window.location.assign(order.checkout_url)
    else { message.value = m.value.unconfirmed; await load() }
  } catch (e) { error.value = failure(e) } finally { busy.value = false }
}
async function redeem() {
  const code = redeemCode.value.trim()
  if (busy.value || !code) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const result = await redeemMembershipCode(code)
    redeemCode.value = ''; message.value = `${m.value.redeemed} +${result.credits}`
    await load(); app.creditsChanged()
  } catch (e) { error.value = e.message || failure(e) } finally { busy.value = false }
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
      <section class="membership">
        <h3>{{ m.recharge }}</h3><p>{{ m.paymentNotice }}</p>
        <div class="plans"><article><strong>{{ m.oneYuan }}</strong><label>{{ m.creditCount }}<input v-model.number="rechargeCredits" type="number" :min="state.minimum_recharge" :max="state.maximum_recharge" step="1" :disabled="busy" /></label><b>{{ money(Number(rechargeCredits || 0) * state.price_per_credit_fen) }}</b><span>{{ m.rechargeRange.replace('{min}', state.minimum_recharge).replace('{max}', state.maximum_recharge) }}</span><button type="button" :disabled="busy || !state.payment_enabled" @click="buy">{{ state.payment_enabled ? m.pay : m.pending }}</button></article></div>
        <p>{{ m.rechargeRules }}</p>
        <label class="redeem"><span>{{ m.redeem }}</span><input v-model="redeemCode" :disabled="busy" maxlength="64" autocomplete="off" :placeholder="m.redeemPlaceholder" /><button type="button" :disabled="busy || !redeemCode.trim()" @click="redeem">{{ m.redeemAction }}</button></label>
      </section>
    </template>
  </section>
</template>

<style scoped>
.credits-panel{color:var(--text-secondary);font-size:13px;line-height:1.65;min-width:0}.credits-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.credits-heading h2{font-size:19px;color:var(--text-primary);margin:0}.credits-panel button{border:1px solid var(--border-dim);border-radius:10px;background:var(--bg-glass);color:var(--text-primary);padding:9px 13px;cursor:pointer}.credits-panel button:disabled{opacity:.5;cursor:not-allowed}.credit-summary{display:flex;align-items:baseline;flex-wrap:wrap;gap:12px;margin:22px 0}.credit-total{font-size:38px;color:var(--neon-blue)}.credits-panel .checkin-button{background:var(--grad-btn);color:white}.credits-error{color:#e85c5c}.membership{margin-top:24px;padding-top:20px;border-top:1px solid var(--border-dim)}.membership h3{margin:0;color:var(--text-primary);font-size:16px}.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:12px 0}.plans article{display:grid;gap:7px;padding:13px;border:1px solid var(--border-dim);border-radius:10px}.plans b{font-size:20px;color:var(--text-primary)}.plans span{font-size:12px}.plans button{width:max-content}.redeem{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:12px}.redeem span{flex-basis:100%;font-weight:600;color:var(--text-primary)}.redeem input{min-width:180px;flex:1;padding:9px;border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-glass);color:var(--text-primary)}
</style>
