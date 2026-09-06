/**
 * The single FE/BE boundary. Every network call in the application lives here.
 * No organ may call fetch() directly.
 *
 * PHASE 1 -> 3:  USE_MOCKS = true   both frontend devs build every organ with
 *                                   the backend switched off.
 * PHASE 4:       USE_MOCKS = false  integration. Any shape mismatch is fixed
 *                                   in the BACKEND, never by editing the
 *                                   contract - the contract is authoritative.
 */

// Env-driven so a static deploy needs no source edit:
//   local / demo laptop -> unset  -> false -> real backend on the same origin
//   Vercel static build -> VITE_USE_MOCKS=true -> fixtures, no backend needed
// The fixtures are generated FROM the engines, so the hosted build shows the
// same numbers the real system computes.
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

import graphMock from './mocks/graph.json'
import caseMock from './mocks/case.json'
import casesMock from './mocks/cases.json'
import timelineMock from './mocks/timeline.json'
import riskMock from './mocks/risk.json'
import dilutionMock from './mocks/dilution.json'
import evidenceMock from './mocks/evidence.json'
import auditMock from './mocks/audit.json'
import healthMock from './mocks/health.json'
import anomalyMock from './mocks/anomaly.json'
import auditVerifyMock from './mocks/audit_verify.json'

const LATENCY_MS = 220 // keeps loading states honest while mocking

const mock = (data) =>
  new Promise((resolve) =>
    setTimeout(() => resolve(structuredClone(data)), LATENCY_MS)
  )

/* ------------------------------------------------------------------- auth */

// Kept in sessionStorage, not localStorage: a shared workstation should not
// leave an officer signed in after the browser closes.
const TOKEN_KEY = 'vm.token'

export const getToken = () => {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}
const setToken = (t) => {
  try { t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY) }
  catch { /* private mode */ }
}

export const authHeader = () => {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export async function login(userId, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, password }),
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail
    throw new Error(detail ?? 'Sign-in failed')
  }
  const body = await res.json()
  setToken(body.token)
  return body
}

export const logout = () => setToken(null)

export const whoami = () => req('/api/auth/me')

async function req(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    ...options,
  })
  if (res.status === 401) {
    // The session is gone. Clear it so the shell shows the sign-in screen
    // rather than a wall of failed panels.
    setToken(null)
    throw new Error('SESSION_EXPIRED')
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.json()
}

/* ------------------------------------------------------------------ system */

export const getHealth = () =>
  USE_MOCKS ? mock(healthMock) : req('/api/health')

/* ------------------------------------------------------------------- cases */

export const listCases = () =>
  USE_MOCKS ? mock(casesMock) : req('/api/cases')

export const getCase = (caseId) =>
  USE_MOCKS ? mock(caseMock) : req(`/api/cases/${caseId}`)

export const createCase = (payload) =>
  USE_MOCKS
    ? mock({ ...caseMock, ...payload })
    : req('/api/cases', { method: 'POST', body: JSON.stringify(payload) })

export const updateCase = (caseId, payload) =>
  USE_MOCKS
    ? mock({ ...caseMock, ...payload })
    : req(`/api/cases/${caseId}`, { method: 'PUT', body: JSON.stringify(payload) })

/* ---------------------------------------------------------------- evidence */

export const listEvidence = (caseId) =>
  USE_MOCKS ? mock(evidenceMock) : req(`/api/cases/${caseId}/evidence`)

/**
 * Evidence upload is multipart, not JSON, and carries the browser-computed
 * SHA-256. The server re-hashes and rejects the file if the two disagree.
 */
export async function uploadEvidence(
  caseId, file, sha256Client, uploadedBy, isSynthetic = true
) {
  if (USE_MOCKS) return mock(evidenceMock[0])
  const form = new FormData()
  form.append('file', file)
  form.append('sha256_client', sha256Client)
  form.append('is_synthetic', String(isSynthetic))
  form.append('uploaded_by', uploadedBy ?? 'IO_SHARMA')
  const res = await fetch(`/api/cases/${caseId}/evidence`, {
    method: 'POST',
    // No Content-Type: the browser sets the multipart boundary. The auth
    // header still has to go on explicitly.
    headers: authHeader(),
    body: form,
  })
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Upload failed')
  return res.json()
}

/**
 * Hash a file in the browser BEFORE it is uploaded, using Web Crypto.
 * This is the first link in the chain of custody.
 */
export async function hashFile(file) {
  const buf = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

/* ------------------------------------------------------------------- graph */

export const runTrace = (caseId, body) =>
  USE_MOCKS
    ? mock({
        case_id: caseId,
        seed: body.seed,
        stats: graphMock.stats,
        node_ids: graphMock.elements.nodes.map((n) => n.data.id),
        edge_ids: graphMock.elements.edges.map((e) => e.data.id),
      })
    : req(`/api/cases/${caseId}/trace`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

/**
 * Omit `seed`/`mode` for the case's own synthetic graph. Passing them renders
 * a live mainnet trace WITHOUT mutating the stored case, so experimenting on
 * stage can never damage the scripted demo path.
 */
export const getGraph = (caseId, seed = null, mode = 'synthetic') => {
  if (USE_MOCKS) return mock(graphMock)
  const q = new URLSearchParams()
  if (seed) q.set('seed', seed)
  if (mode) q.set('data_mode', mode)
  const qs = q.toString()
  return req(`/api/cases/${caseId}/graph${qs ? `?${qs}` : ''}`)
}

export const getLabel = (address) =>
  USE_MOCKS ? mock(null) : req(`/api/labels/${address}`)

/* -------------------------------------------------------- risk / dilution */

export function getRisk(caseId, nodeId) {
  if (!USE_MOCKS) return req(`/api/cases/${caseId}/nodes/${nodeId}/risk`)
  if (nodeId.toLowerCase() === riskMock.node_id.toLowerCase()) return mock(riskMock)

  const node = graphMock.elements.nodes.find(
    (n) => n.data.id.toLowerCase() === nodeId.toLowerCase()
  )
  if (!node) return Promise.reject(new Error(`Node ${nodeId} not found`))
  return mock({
    node_id: node.data.id,
    case_id: caseId,
    score: node.data.risk_score,
    level: node.data.risk_level,
    illicit_ratio: node.data.illicit_ratio,
    indicators: [],
    engine_version: 'risk-1.0',
    computed_at: graphMock.stats.traced_at,
  })
}

export const getDilution = (caseId) =>
  USE_MOCKS
    ? mock(dilutionMock)
    : req(`/api/cases/${caseId}/dilution`, { method: 'POST' })

/* ------------------------------------------------- timeline / audit / report */

export const getTimeline = (caseId) =>
  USE_MOCKS ? mock(timelineMock) : req(`/api/cases/${caseId}/timeline`)

export const getAudit = (caseId) =>
  USE_MOCKS ? mock(auditMock) : req(`/api/cases/${caseId}/audit`)

/** Re-walks the hash chain. Reports the first broken link, if any. */
export const verifyAudit = (caseId) =>
  USE_MOCKS ? mock(auditVerifyMock) : req(`/api/cases/${caseId}/audit/verify`)

export const generateReport = (caseId) =>
  USE_MOCKS
    ? Promise.reject(new Error('Report Engine lands in Phase 5'))
    : req(`/api/cases/${caseId}/report`, { method: 'POST' })

/* ----------------------------------------------------------------- helpers */

export const DEMO_CASE_ID = 'CP-CYBER-2026-001'
export const DILUTION_THRESHOLD = 0.3

export const riskColor = (level) =>
  ({
    CRITICAL: '#e5484d',
    HIGH: '#e5901d',
    MEDIUM: '#d9b21c',
    LOW: '#3d9a6d',
  }[level] ?? '#6b6579')

export const inr = (n) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n)

/* ------------------------------------------- flag agent (ML) / STR draft */

/**
 * Unsupervised anomaly findings. Deliberately a SEPARATE call from getRisk:
 * a model finding must never be rendered as a statutory risk score.
 */
export const getAnomaly = (caseId) =>
  USE_MOCKS ? mock(anomalyMock) : req(`/api/cases/${caseId}/anomaly`)

/** Generates a DRAFT STR. There is no filing endpoint, by design. */
export const generateSTR = (caseId) =>
  USE_MOCKS
    ? Promise.reject(new Error('STR generation requires the backend'))
    : req(`/api/cases/${caseId}/str`, { method: 'POST' })

/* ------------------------------------------------------------ asset ledger */

/* Which currency moved, at which layer, and what it is in rupees.
   Never blocks the case view - App treats a failure here as a missing panel. */
export const getAssets = (caseId) =>
  USE_MOCKS ? mock(null) : req(`/api/cases/${caseId}/assets`)

export const getNodeAssets = (caseId, nodeId) =>
  USE_MOCKS ? mock(null) : req(`/api/cases/${caseId}/assets/nodes/${nodeId}`)
