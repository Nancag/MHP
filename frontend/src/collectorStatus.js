// A connection indicator only; never use extension messages for authentication.
export function createCollectorProbe(target, onChange, timeoutMs = 1800) {
  let pending = '', timer = null, disposed = false
  function check() {
    if (disposed) return
    target.clearTimeout(timer)
    pending = target.crypto.randomUUID()
    onChange({state: 'checking', version: ''})
    timer = target.setTimeout(() => {
      pending = ''
      onChange({state: 'missing', version: ''})
    }, timeoutMs)
    target.postMessage({type: 'MHP_COLLECTOR_PING', nonce: pending}, target.location.origin)
  }
  function receive(event) {
    if (disposed || event.source !== target || event.origin !== target.location.origin) return
    const packet = event.data
    if (packet?.type === 'MHP_COLLECTOR_AVAILABLE') { check(); return }
    if (!pending || packet?.type !== 'MHP_COLLECTOR_READY' || packet.nonce !== pending ||
        packet.protocol !== 1 || typeof packet.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(packet.version)) return
    target.clearTimeout(timer)
    pending = ''
    const version=packet.version.split('.').map(Number)
    const current=version[0]>0||version[1]>=3
    onChange({state: current?'installed':'outdated', version: packet.version})
  }
  target.addEventListener('message', receive)
  return {check, dispose() {
    disposed = true
    target.clearTimeout(timer)
    target.removeEventListener('message', receive)
  }}
}
