import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import { AppProvider, Any, api, post, useApp } from './lib'
import './trace'
import { Documents, Findings, Overview, ReturnPage } from './pages/core'
import { Schedules } from './pages/schedules'
import { ClientPortal, Compare, Filing, Firm, People, Review, Timeline } from './pages/work'

const NAV: [string, string, string][] = [
  ['Work', 'overview', 'Overview'], ['Work', 'findings', 'Findings'], ['Work', 'review', 'Review'], ['Work', 'people', 'People'],
  ['Evidence', 'return', 'Return'], ['Evidence', 'documents', 'Documents'], ['Evidence', 'schedules', 'Schedules'], ['Evidence', 'compare', 'Compare & what-if'],
  ['Season', 'filing', 'Filing & after'], ['Season', 'timeline', 'Timeline'], ['Firm', 'firm', 'Firm'],
]

function Shell() {
  const { boot, st, page, go, person, setPerson, live, name, role, trace, send } = useApp()
  const [q, setQ] = useState('')
  const [res, setRes] = useState<Any[]>([])
  const seenRef = useRef<number>(0)
  useEffect(() => { if (!q || q.length < 2 || role === 'client') { setRes([]); return } const t = setTimeout(() => api('/api/search?q=' + encodeURIComponent(q)).then(setRes).catch(() => setRes([])), 200); return () => clearTimeout(t) }, [q])
  // mark "seen" when the person looks at the overview, so "changes since I last looked" means something
  // 'Seen' is recorded only when the person clicks 'Mark all as seen' (Timeline → since)
  if (!boot || !st) return <div className="empty">Loading workpaper…</div>
  const client = role === 'client'
  const counts: Record<string, Any> = {
    findings: st.findings?.filter((f: Any) => f.status === 'open' && f.severity !== 'info').length,
    review: st.notes?.filter((n: Any) => n.blocking && n.status === 'open').length,
    people: st.questions?.filter((q: Any) => q.status === 'open').length,
  }
  const pick = (r: Any) => { setQ(''); setRes([]); if (r.type === 'line') trace({ kind: 'line', id: r.id }); else if (r.type === 'doc') trace({ kind: 'doc', id: r.id }); else if (r.type === 'finding') go('findings', r.id); else trace({ kind: 'evidence', ref: { type: r.type, id: r.id } }) }
  return <div className="app">
    <aside className="side">
      <div className="brand"><b>Miraflores Workpaper</b><span>Okafor-Lindqvist · 2025 · {boot.packet.client_id}</span></div>
      <nav className="nav">{client ? <><div className="grp">Client portal</div><button className="on">My return</button></> :
        NAV.map(([g, k, l], i) => <React.Fragment key={k}>{(i === 0 || NAV[i - 1][0] !== g) && <div className="grp">{g}</div>}
          <button className={page === k ? 'on' : ''} onClick={() => go(k)}>{l}{counts[k] ? <span className={'cnt ' + (k === 'review' ? 'red' : '')}>{counts[k]}</span> : null}</button></React.Fragment>)}</nav>
      <div style={{ marginTop: 'auto', padding: 14, fontSize: 11.5, color: '#8fb0b0' }}>Packet loaded as delivered · every change is an event · nothing is overwritten</div>
    </aside>
    <div className="main">
      <div className="top">
        {!client && <div className="search"><span className="ico">⌕</span><input placeholder="Search lines, documents, findings, notes, client answers…" value={q} onChange={e => setQ(e.target.value)} />
          {res.length > 0 && <div className="results">{res.map((r, i) => <div key={i} onClick={() => pick(r)}><span className="chip">{r.type}</span> {r.title} <span className="muted small">{String(r.sub).slice(0, 60)}</span></div>)}</div>}</div>}
        <span className="sp" />
        {!client && st.changes.count > 0 && <button className="chip acc" onClick={() => go('timeline', 'since')}>{st.changes.count} changes since you last looked</button>}
        <span className="live"><i style={{ background: live ? 'var(--ok)' : '#c9ccd1' }} />{live ? 'live' : 'offline'}</span>
        <div className="who"><span className="small muted">Viewing as</span>
          <select value={person} onChange={e => { setPerson(e.target.value); if (boot.people.find((p: Any) => p.id === e.target.value)?.kind === 'client') go('overview') }}>
            {boot.people.map((p: Any) => <option key={p.id} value={p.id}>{p.name} — {p.role.replace('_', ' ')}{p.kind === 'staff' && !p.sensitive_data_clearance ? ' (no clearance)' : ''}</option>)}</select></div>
      </div>
      <div className="content">{client ? <ClientPortal /> :
        page === 'findings' ? <Findings /> : page === 'return' ? <ReturnPage /> : page === 'documents' ? <Documents /> : page === 'schedules' ? <Schedules /> :
          page === 'review' ? <Review /> : page === 'people' ? <People /> : page === 'filing' ? <Filing /> : page === 'timeline' ? <Timeline /> :
            page === 'compare' ? <Compare /> : page === 'firm' ? <Firm /> : <Overview />}</div>
    </div>
  </div>
}

createRoot(document.getElementById('root')!).render(<AppProvider><Shell /></AppProvider>)
