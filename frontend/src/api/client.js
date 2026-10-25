export const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function workspaceRequest(path, method='GET', payload, options={}) {
  const res=await apiFetch(`${API_BASE}/api${path}`,{...options,method,...(payload===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})})
  if(!res.ok)throw await responseError(res)
  return res.json()
}

async function apiFetch(input, options = {}) {
  const { timeoutMs = 35000, signal, ...rest } = options
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) controller.abort()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let response
  try {
    response = await fetch(input, { ...rest, signal: controller.signal, credentials: 'include' })
  } catch (cause) {
    const error = new Error(signal?.aborted ? 'CANCELLED' : controller.signal.aborted ? 'TIMEOUT' : 'NETWORK')
    error.code = error.message
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
  if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('mhp:unauthorized'))
  return response
}

async function authRequest(path, body) {
  const response = await fetch(`${API_BASE}/api/auth${path}`, {
    credentials: 'include',
    ...(body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}),
  })
  if (!response.ok) {
    const error = new Error(await readErrorDetail(response))
    error.status = response.status
    throw error
  }
  return response.json()
}

export const fetchAuthConfig = () => authRequest('/config')
export const fetchCurrentUser = () => authRequest('/me')
export const sendEmailCode = (email) => authRequest('/email/code', {email})
export const verifyEmailCode = (payload) => authRequest('/email/verify', payload)
export const logoutUser = () => authRequest('/logout', {})

export function assetPreviewUrl(assetId) {
  return `${API_BASE}/api/assets/${assetId}/preview`
}

async function readErrorDetail(res) {
  try {
    const data = await res.json()
    if (data && typeof data.detail === 'string') {
      return data.detail
    }
  } catch {
    /* 响应体不是 JSON 时忽略 */
  }
  return `请求失败（HTTP ${res.status}）`
}

async function responseError(res) {
  const error=new Error(await readErrorDetail(res))
  error.status=res.status
  return error
}

async function accountRequest(path='',payload) {
  const res=await apiFetch(`${API_BASE}/api/account${path}`,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  if(!res.ok)throw await responseError(res)
  return res.json()
}
export const fetchAccount=()=>accountRequest()
export const claimDailyCheckin=()=>accountRequest('/checkin',{})
export const createMembershipOrder=payload=>accountRequest('/orders',payload)
export const fetchMembershipOrder=id=>accountRequest(`/orders/${encodeURIComponent(id)}`)

export async function fetchAssets(page = 1, pageSize = 24, role = null) {
  const res = await apiFetch(`${API_BASE}/api/assets?page=${page}&page_size=${pageSize}${role?'&role='+encodeURIComponent(role):''}`)
  if (!res.ok) {
    throw await responseError(res)
  }
  return res.json()
}

export async function uploadAsset(file, role = 'product', folderId = null) {
  const form = new FormData()
  form.append('file', file)
  form.append('role', role)
  if (folderId) form.append('folder_id', folderId)
  const res = await apiFetch(`${API_BASE}/api/assets`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    throw await responseError(res)
  }
  return res.json()
}

async function setRequest(path='',body) {
  const res=await apiFetch(`${API_BASE}/api/product-sets${path}`,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  if(!res.ok)throw await responseError(res)
  return res.json()
}
export const fetchSetCapabilities=()=>setRequest('/capabilities')
export const fetchProductSets=()=>setRequest()
export const createProductSet=payload=>setRequest('',payload)
export const fetchProductSet=id=>setRequest(`/${id}`)
export const cancelProductSet=id=>setRequest(`/${id}/cancel`,{})
export const reviewSetPage=(id,gid,payload)=>setRequest(`/${id}/pages/${gid}/review`,payload)
export const retrySetPage=(id,gid,page,confirmSend=false)=>setRequest(`/${id}/pages/${gid}/regenerate`,{page,confirm_send:confirmSend})
export const setDownloadUrl=(id,edge)=>`${API_BASE}/api/product-sets/${id}/download?long_edge=${edge}`

export function generationPreviewUrl(generationId) {
  return `${API_BASE}/api/generations/${generationId}/preview`
}

export async function requestGeneration(payload, signal) {
  const res = await apiFetch(`${API_BASE}/api/generations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal, timeoutMs: 75000,
  })
  if (!res.ok) {
    throw await responseError(res)
  }
  return res.json()
}

export async function fetchGeneration(generationId, signal) {
  const res = await apiFetch(`${API_BASE}/api/generations/${generationId}`, { signal })
  if (!res.ok) {
    throw await responseError(res)
  }
  return res.json()
}

export async function fetchGenerations(filters = {}, page = 1, pageSize = 20) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (filters.assetId) params.set('asset_id', filters.assetId)
  if (filters.genType) params.set('gen_type', filters.genType)
  if (filters.scene) params.set('scene', filters.scene)
  if (filters.platform) params.set('platform', filters.platform)
  if (filters.style) params.set('style', filters.style)
  const res = await apiFetch(`${API_BASE}/api/generations?${params.toString()}`)
  if (!res.ok) {
    throw await responseError(res)
  }
  return res.json()
}

export async function downloadBlob(url, filename) {
  const res = await apiFetch(url)
  if (!res.ok) {
    throw new Error(`下载失败（HTTP ${res.status}）`)
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
}

export async function cancelGeneration(generationId) {
  const res = await apiFetch(`${API_BASE}/api/generations/${generationId}/cancel`, { method: 'POST' })
  if (!res.ok) throw await responseError(res)
  return res.json()
}
