// Used only by older cloud frontend builds. New builds have native Vue links.
(() => {
  if (window.__MHP_NATIVE__) return
  const anchor = document.getElementById('mhp-download-entry')
  if (!anchor) return
  const sync = () => {
    const oldButton = document.querySelector('.hero .auth-buttons button.btn-ghost')
    if (oldButton && /下载客户端|Download Client/.test(oldButton.textContent)) {
      const link = document.createElement('a')
      link.className = oldButton.className
      link.href = '/download.html'
      link.append(...oldButton.childNodes)
      oldButton.replaceWith(link)
    }
    const dialog = document.querySelector('.auth-dialog')
    const nativeLink = document.querySelector(dialog ? '.auth-dialog a[href="/download.html"]' : '.hero a[href="/download.html"]')
    anchor.hidden = !document.querySelector('.hero') || Boolean(nativeLink)
  }
  sync()
  new MutationObserver(sync).observe(document.getElementById('app') || document.body, {childList:true, subtree:true})
})()
