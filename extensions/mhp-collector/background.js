// Make installation detectable in MHP tabs that were already open.
chrome.runtime.onInstalled.addListener(async () => {
  const matches = chrome.runtime.getManifest().host_permissions
  const tabs = await chrome.tabs.query({url: matches})
  await Promise.allSettled(tabs.filter(tab => tab.id !== undefined).map(tab =>
    chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['bridge.js']})))
})
