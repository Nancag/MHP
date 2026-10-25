// Isolated extension context. No product data, account data, or network access.
(() => {
  if (globalThis.mhpCollectorBridge) return
  globalThis.mhpCollectorBridge = true
  window.addEventListener('message', event => {
    if (event.source !== window || event.origin !== location.origin ||
        event.data?.type !== 'MHP_COLLECTOR_PING' ||
        typeof event.data.nonce !== 'string' || event.data.nonce.length > 64) return
    try {
      if (!chrome.runtime.id) return // Removed/disabled extensions must not report ready.
      window.postMessage({type: 'MHP_COLLECTOR_READY', nonce: event.data.nonce,
        protocol: 1, version: chrome.runtime.getManifest().version}, location.origin)
    } catch {} // The extension may have been reloaded or disabled.
  })
  window.postMessage({type: 'MHP_COLLECTOR_AVAILABLE'}, location.origin)
})()
