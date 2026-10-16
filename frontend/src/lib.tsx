import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

export type Any = any

// ---------------------------------------------------------------- api
let currentPerson = (() => { try { return localStorage.getItem('wp.person') || 'st-01' } catch { return 'st-01' } })()
export const getPerson = () => currentPerson
export function setPersonGlobal(p: string) { currentPerson = p; try { localStorage.setItem('wp.person', p) } catch {} }

export async function api(path: string, opts: RequestInit = {}): Promise<Any> {
  const r = await fetch(path, { ...opts, headers: { 'X-Person': currentPerson, ...(opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(opts.headers || {}) } })
  const text = await r.text()
  let data: Any = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!r.ok) throw new Error((data && data.detail) || r.statusText)
  return data
}
export const post = (path: string, body: Any) => api(path, { method: 'POST', body: JSON.stringify(body) })

// ---------------------------------------------------------------- formatting
export const money = (v: Any, dec = 0) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v !== 'number') return String(v)
  const s = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
  return v < 0 ? `(${s})` : s
}
export const signed = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '±') + Math.abs(Math.round(v)).toLocaleString('en-US')
export const fmtVal = (v: Any) => typeof v === 'number' ? (Number.isInteger(v) || Math.abs(v) >= 1000 ? money(v, Math.abs(v) < 10 && !Number.isInteger(v) ? 4 : (Number.isInteger(v) ? 0 : 2)) : v.toString()) : (v === null || v === undefined ? '—' : String(v))
export const dt = (s: string) => s ? s.replace('T', ' ').replace(/:\d\dZ$/, '').replace('Z', '') : ''
export const day = (s: string) => s ? s.slice(0, 10) : ''

// ---------------------------------------------------------------- context
type Ctx = {
  boot: Any; st: Any; person: string; setPerson: (p: string) => void; refresh: () => Promise<void>;
  go: (page: string, arg?: Any) => void; page: string; arg: Any;
  trace: (t: Any) => void; send: (events: Any[] | Any, label?: string) => Promise<Any>;
  toast: (msg: string, batch?: string) => void; ask: (cfg: AskCfg) => Promise<Any>;
  name: (id: string) => string; role: string; live: boolean; tick: number;
}
const C = createContext<Ctx>(null as Any)
export const useApp = () => useContext(C)

export type AskField = { key: string; label: string; type?: 'text' | 'textarea' | 'select' | 'number'; options?: string[]; value?: Any; required?: boolean }
export type AskCfg = { title: string; text?: string; fields: AskField[]; ok?: string }

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [boot, setBoot] = useState<Any>(null)
  const [st, setSt] = useState<Any>(null)
  const [person, setP] = useState(getPerson())
  const [route, setRoute] = useState<{ page: string; arg: Any }>(() => {
    const h = location.hash.replace('#', '').split('/')
    return { page: h[0] || 'overview', arg: h[1] ? decodeURIComponent(h.slice(1).join('/')) : null }
  })
  const [traceT, setTrace] = useState<Any>(null)
  const [toastS, setToast] = useState<Any>(null)
  const [askS, setAsk] = useState<Any>(null)
  const [live, setLive] = useState(false)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(async () => {
    const s = await api('/api/state')
    setSt(s); setTick(t => t + 1)
  }, [])

  useEffect(() => { api('/api/bootstrap').then(setBoot) }, [])
  useEffect(() => { refresh() }, [person, refresh])
  useEffect(() => {
    const es = new EventSource('/api/stream')
    let timer: Any = null
    es.onopen = () => setLive(true)
    es.onerror = () => setLive(false)
    es.onmessage = () => { clearTimeout(timer); timer = setTimeout(() => refresh(), 250) }
    return () => es.close()
  }, [refresh])
  useEffect(() => {
    const on = () => {
      const h = location.hash.replace('#', '').split('/')
      setRoute({ page: h[0] || 'overview', arg: h[1] ? decodeURIComponent(h.slice(1).join('/')) : null })
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const go = (page: string, arg?: Any) => { location.hash = page + (arg ? '/' + encodeURIComponent(arg) : '') }
  const setPerson = (p: string) => { setPersonGlobal(p); setP(p); setTrace(null) }
  const toast = (msg: string, batch?: string) => { setToast({ msg, batch, id: Math.random() }); }
  useEffect(() => { if (!toastS) return; const t = setTimeout(() => setToast(null), 7000); return () => clearTimeout(t) }, [toastS])

  const send = async (events: Any[] | Any, label?: string) => {
    const list = Array.isArray(events) ? events : [events]
    try {
      const r = await post('/api/events', { events: list })
      await refresh()
      if (label) toast(label, r.batch || (list.length === 1 && r.written?.[0]?.batch) || undefined)
      return r
    } catch (e: Any) { toast('⚠ ' + e.message); throw e }
  }
  const ask = (cfg: AskCfg) => new Promise<Any>((resolve) => setAsk({ cfg, resolve }))
  const name = (id: string) => {
    if (!boot) return id
    const p = boot.people.find((x: Any) => x.id === id)
    return p ? p.name : id === 'client' ? 'Client' : id
  }
  const role = st?.role || boot?.people.find((x: Any) => x.id === person)?.role || ''

  return (
    <C.Provider value={{ boot, st, person, setPerson, refresh, go, page: route.page, arg: route.arg, trace: setTrace, send, toast, ask, name, role, live, tick }}>
      {children}
      {traceT && <TraceSlot t={traceT} close={() => setTrace(null)} />}
      {toastS && <div className="toast"><span>{toastS.msg}</span>{toastS.batch && <button onClick={async () => { await post('/api/events', { events: [{ type: 'batch.undo', payload: { batch: toastS.batch } }] }); setToast(null); refresh() }}>Undo</button>}</div>}
      {askS && <AskModal cfg={askS.cfg} done={(v: Any) => { setAsk(null); askS.resolve(v) }} />}
    </C.Provider>
  )
}

// The trace drawer is rendered from a registry to avoid circular imports.
let TraceImpl: Any = () => null
export const registerTrace = (c: Any) => { TraceImpl = c }
function TraceSlot({ t, close }: Any) { return <><div className="scrim" onClick={close} /><div className="drawer"><TraceImpl t={t} close={close} /></div></> }

function AskModal({ cfg, done }: { cfg: AskCfg; done: (v: Any) => void }) {
  const [v, setV] = useState<Any>(() => Object.fromEntries(cfg.fields.map(f => [f.key, f.value ?? (f.type === 'select' ? f.options?.[0] : '')])))
  const ok = cfg.fields.every(f => !f.required || (v[f.key] !== '' && v[f.key] !== undefined))
  return (
    <div className="modal" onClick={() => done(null)}>
      <div className="box" onClick={e => e.stopPropagation()}>
        <h2 style={{ marginTop: 0 }}>{cfg.title}</h2>
        {cfg.text && <p className="muted">{cfg.text}</p>}
        {cfg.fields.map(f => (
          <label key={f.key} className="small">{f.label}{f.required && ' *'}
            {f.type === 'textarea' ? <textarea rows={4} value={v[f.key]} onChange={e => setV({ ...v, [f.key]: e.target.value })} autoFocus /> :
              f.type === 'select' ? <select value={v[f.key]} onChange={e => setV({ ...v, [f.key]: e.target.value })}>{f.options!.map(o => <option key={o}>{o}</option>)}</select> :
                <input type={f.type === 'number' ? 'number' : 'text'} value={v[f.key]} onChange={e => setV({ ...v, [f.key]: e.target.value })} />}
          </label>
        ))}
        <div className="row"><span className="sp" /><button className="btn" onClick={() => done(null)}>Cancel</button><button className="btn pri" disabled={!ok} onClick={() => done(v)}>{cfg.ok || 'Save'}</button></div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- small components
export const Sev = ({ s }: { s: string }) => <span className={'chip ' + ({ error: 'err', warning: 'warn', review: 'rev', info: '' } as Any)[s]}>{s}</span>

export function Ref({ r, children }: { r: Any; children?: React.ReactNode }) {
  const { trace, go, boot } = useApp()
  const t = r.type
  const label = children || (t === 'line' ? r.id : t === 'ev' ? `${r.doc || ''} ${r.id}` : t === 'doc' ? `${r.id}${r.page ? ' p' + r.page : ''}` : t === 'qa' ? r.id : t === 'msg' ? r.id : t === 'call' ? 'call 3/26' : t === 'agency' ? 'agency' + r.id : t === 'py' ? 'prior year' : t === 'whatif' ? 'what-if' : t === 'household' ? 'household' : r.id)
  const onClick = () => {
    if (t === 'line') trace({ kind: 'line', id: r.id })
    else if (t === 'ev') trace({ kind: 'doc', id: r.doc || r.id, page: r.page, ev: r.id })
    else if (t === 'doc') trace({ kind: 'doc', id: r.id, page: r.page })
    else if (t === 'finding') go('findings', r.id)
    else trace({ kind: 'evidence', ref: r })
  }
  const cls = { line: 'acc', ev: 'warn', doc: '', qa: 'rev', msg: 'rev', call: 'rev' } as Any
  return <button className={'chip ' + (cls[t] || '')} onClick={onClick} title={t}>{label}</button>
}

export function Num({ k, v, adj }: { k: string; v: Any; adj?: Any }) {
  const { trace } = useApp()
  const changed = adj !== undefined && adj !== null && typeof v === 'number' && Math.abs(adj - v) > 0.004
  return <a className="num" onClick={() => trace({ kind: 'line', id: k })} style={{ cursor: 'pointer' }} title={'Trace ' + k}>
    {changed ? <><span className="strike">{fmtVal(v)}</span> {fmtVal(adj)}</> : fmtVal(v)}
  </a>
}

export function useLoad<T = Any>(path: string | null, deps: Any[] = []): [T | null, () => void] {
  const { tick, person } = useApp()
  const [d, setD] = useState<T | null>(null)
  const [n, setN] = useState(0)
  useEffect(() => { if (!path) return; let ok = true; api(path).then(x => ok && setD(x)).catch(() => ok && setD(null)); return () => { ok = false } }, [path, tick, person, n, ...deps])
  return [d, () => setN(x => x + 1)]
}

export const can = (role: string, what: string) => {
  const m: Record<string, string[]> = {
    propose: ['preparer', 'reviewer', 'partner'], verify: ['preparer', 'reviewer', 'partner'], approve: ['reviewer', 'partner'],
    review_note: ['reviewer', 'partner', 'quality_reviewer'], ask: ['preparer', 'reviewer', 'partner'], standards: ['firm_administrator'],
    file: ['partner'], admin: ['firm_administrator', 'partner'], judgment: ['preparer', 'reviewer', 'partner'],
  }
  return (m[what] || []).includes(role)
}

export function useOnce(fn: () => void) { const r = useRef(false); useEffect(() => { if (!r.current) { r.current = true; fn() } }, []) }

export const AREA_ORDER = ['intake_and_engagement', 'wages_and_stock_compensation', 'investments_and_digital_assets', 'business', 'rentals_and_sale', 'pass_throughs_and_basis', 'deductions_and_credits', 'payments_and_penalties', 'california', 'return_summary']
