import React, { useMemo, useState } from 'react'
import { AREA_ORDER, Any, Num, Ref, Sev, can, dt, fmtVal, money, signed, useApp, useLoad } from '../lib'
import { DocView, useActions } from '../trace'

// ---------------------------------------------------------------- Overview
export function Overview() {
  const { st, boot, go, name, person } = useApp()
  if (!st || !boot) return null
  const s = st.summary
  const open = st.findings.filter((f: Any) => f.status === 'open')
  const sevCount = (sv: string) => open.filter((f: Any) => f.severity === sv).length
  const valid = (area: string, level: string) => st.signoffs.find((x: Any) => x.area === area && x.level === level)
  return <div>
    <h1>{boot.packet.name}</h1>
    <p className="sub">Client {boot.packet.client_id} · MFJ · CA → TX on 7/15/2025 · engine {boot.packet.current_version} computed {dt(boot.packet.versions.at(-1).computed_at)} · packet sha256 {boot.packet.sha256.slice(0, 12)}… loaded as delivered</p>
    {st.filing.frozen_at && <div className="banner frozen">Return frozen at filing ({dt(st.filing.frozen_at)}). Changes require an amendment.</div>}
    <div className="grid g4">
      <Kpi label="Federal balance due (engine v3)" v={s.engine.federal.balance_due} />
      <Kpi label="Federal — workpaper (approved)" v={s.approved.federal.balance_due} d={s.approved.federal.balance_due - s.engine.federal.balance_due} note={`total tax ${money(s.approved.federal.total_tax)} (${signed(s.approved.federal.change)})`} />
      <Kpi label="California balance due (engine v3)" v={s.engine.california.balance_due} />
      <Kpi label="California — workpaper (approved)" v={s.approved.california.balance_due} d={s.approved.california.balance_due - s.engine.california.balance_due} note={`total tax ${money(s.approved.california.total_tax)} (${signed(s.approved.california.change)})`} />
    </div>
    <p className="small muted">Negative = refund. Workpaper totals = engine + Σ approved adjustments × the packet's per-dollar tax-effect rates; pending adjustments would move federal to {money(s.with_proposed.federal.balance_due)} and California to {money(s.with_proposed.california.balance_due)}. Large changes cross thresholds, so the engine recompute is the final number.</p>
    <div className="grid g3" style={{ marginTop: 14 }}>
      <div className="card"><div className="row"><h2 style={{ margin: 0 }}>Ready to file?</h2><span className="sp" /><span className="chip">{st.steps.filter((x: Any) => x.done).length}/{st.steps.length}</span></div>
        <ul className="steps">{st.steps.map((x: Any) => <li key={x.step}><span className={'dot ' + (x.done ? 'ok' : 'no')} />{x.step}<div className="small muted" style={{ marginLeft: 15 }}>{x.detail}</div></li>)}</ul></div>
      <div className="card"><div className="row"><h2 style={{ margin: 0 }}>Findings</h2><span className="sp" /><button className="btn sm" onClick={() => go('findings')}>Open</button></div>
        <div className="row" style={{ margin: '8px 0' }}><span className="chip err">{sevCount('error')} errors</span><span className="chip warn">{sevCount('warning')} warnings</span><span className="chip rev">{sevCount('review')} judgment</span><span className="chip ok">{st.findings.length - open.length} resolved</span></div>
        {open.filter((f: Any) => f.severity !== 'info').slice(0, 7).map((f: Any) => <div key={f.id} className="small" style={{ margin: '5px 0', cursor: 'pointer' }} onClick={() => go('findings', f.id)}><Sev s={f.severity} /> {f.title}</div>)}</div>
      <div className="card"><div className="row"><h2 style={{ margin: 0 }}>For {name(person)}</h2><span className="sp" /><span className="chip">{st.inbox.filter((x: Any) => x.kind !== 'deadline').length}</span></div>
        {st.inbox.filter((x: Any) => x.kind !== 'deadline').slice(0, 7).map((x: Any, i: number) => <div key={i} className="small" style={{ margin: '5px 0' }}><span className="chip">{x.kind.replace(/_/g, ' ')}</span> {x.text}</div>)}
        {st.changes.count > 0 && <div className="banner info small" style={{ marginTop: 8 }}>{st.changes.count} changes by others since you last looked. <a onClick={() => go('timeline', 'since')} style={{ cursor: 'pointer' }}>See them</a></div>}
        <h3>Deadlines</h3>{boot.firm.deadlines.map((d: Any) => <div key={d.what} className="small"><span className="num">{d.date}</span> {d.what}</div>)}</div>
    </div>
    <h2>Work areas</h2>
    <table className="t card"><thead><tr><th>Area</th><th>Open findings</th><th>Adjustments</th><th>Preparer</th><th>Reviewer</th><th>Time / budget</th></tr></thead><tbody>
      {AREA_ORDER.filter(a => a !== 'return_summary').map(a => {
        const f = open.filter((x: Any) => x.area === a && x.severity !== 'info').length
        const adj = st.adjustments.filter((x: Any) => x.area === a && x.status !== 'reversed')
        const t = st.time.rows.find((r: Any) => r.area === a)
        const so = (lvl: string) => { const x = valid(a, lvl); return x ? <span className={'chip ' + (x.valid ? 'ok' : 'err')}>{x.valid ? '✓ ' : '↺ reopened · '}{name(x.by).split(' ')[0]}</span> : <span className="chip">—</span> }
        return <tr key={a} className="click" onClick={() => go('review', a)}><td>{boot.areas[a]}</td><td>{f ? <span className="chip warn">{f}</span> : <span className="chip ok">0</span>}</td>
          <td>{adj.length} <span className="muted small">({adj.filter((x: Any) => x.status === 'proposed').length} pending)</span></td><td>{so('preparer')}</td><td>{so('reviewer')}</td>
          <td style={{ width: 160 }}>{t ? <><div className="bar"><i className={t.spent > t.budget ? 'over' : ''} style={{ width: Math.min(100, (t.spent / (t.budget || 1)) * 100) + '%' }} /></div><span className="small muted">{t.spent} / {t.budget} h</span></> : <span className="muted small">—</span>}</td></tr>
      })}</tbody></table>
  </div>
}

function Kpi({ label, v, d, note }: Any) {
  return <div className="card kpi"><div className="lbl">{label}</div><div className="val">{money(v)}</div>
    {d !== undefined && <div className={'delta ' + (d < 0 ? 'diffpos' : d > 0 ? 'diffneg' : 'muted')}>{d === 0 ? 'no change' : `${signed(d)} vs engine`}</div>}{note && <div className="small muted">{note}</div>}</div>
}

// ---------------------------------------------------------------- Findings
export function Findings() {
  const { st, boot, arg, send, ask, role, go } = useApp()
  const [filter, setFilter] = useState('open')
  const [sel, setSel] = useState<Set<string>>(new Set())
  if (!st || !boot) return null
  const list = st.findings.filter((f: Any) => (filter === 'all' || (filter === 'open' ? f.status === 'open' : filter === 'engine' ? f.kind === 'engine_diagnostic' : f.status !== 'open')))
    .sort((a: Any, b: Any) => (a.id === arg ? -1 : b.id === arg ? 1 : 0) || ['error', 'warning', 'review', 'info'].indexOf(a.severity) - ['error', 'warning', 'review', 'info'].indexOf(b.severity))
  const accept = async (fs: Any[]) => {
    const v = await ask({ title: fs.length > 1 ? `Accept ${fs.length} findings` : 'Accept finding', text: 'Accepting records the finding as valid and proposes its adjustments for review. One undo reverses the whole batch.', fields: [{ key: 'reason', label: 'Reason / evidence', type: 'textarea', value: fs.length === 1 ? fs[0].summary.slice(0, 400) : 'Agreed to source documents cited in each finding', required: true }] })
    if (!v) return
    const evs: Any[] = []
    fs.forEach(f => {
      evs.push({ type: 'finding.accepted', payload: { id: f.id, reason: v.reason } })
      f.proposed.forEach((p: Any) => evs.push({ type: 'adjustment.proposed', payload: { line: p.line, delta: p.delta, category: p.category, description: p.description, reason: v.reason, finding: f.id, evidence: f.refs.slice(0, 4) } }))
    })
    await send(evs, `${fs.length} finding(s) accepted, ${evs.length - fs.length} adjustment(s) proposed`)
    setSel(new Set())
  }
  const dismiss = async (f: Any) => {
    const v = await ask({ title: 'Dismiss finding', fields: [{ key: 'reason', label: 'Why this is not an error', type: 'textarea', required: true }, { key: 'authority', label: 'Authority (if a judgment)' }] })
    if (v) send({ type: 'finding.dismissed', payload: { id: f.id, reason: v.reason, authority: v.authority } }, 'Finding dismissed')
  }
  const tot = list.reduce((a: Any, f: Any) => ({ fed: a.fed + (f.status === 'open' ? f.est_fed : 0), ca: a.ca + (f.status === 'open' ? f.est_ca : 0) }), { fed: 0, ca: 0 })
  return <div>
    <h1>Findings</h1>
    <p className="sub">Independent checks read the printed documents, prior year and agency records directly — they never trust the engine. Engine diagnostics are listed too, but they missed every error below.</p>
    <div className="row" style={{ marginBottom: 10 }}>
      <div className="tabs" style={{ margin: 0, border: 0 }}>{['open', 'resolved', 'engine', 'all'].map(x => <button key={x} className={filter === x ? 'on' : ''} onClick={() => setFilter(x)}>{x}</button>)}</div>
      <span className="sp" /><span className="small">Open estimated effect: federal <b className="num">{signed(tot.fed)}</b> · CA <b className="num">{signed(tot.ca)}</b></span>
      {can(role, 'propose') && sel.size > 0 && <button className="btn pri" onClick={() => accept(st.findings.filter((f: Any) => sel.has(f.id)))}>Accept {sel.size} selected</button>}
    </div>
    {list.map((f: Any) => <div key={f.id} className={`card finding ${f.severity} ${f.status !== 'open' ? 'done' : ''}`} style={{ marginBottom: 10, outline: f.id === arg ? '2px solid var(--accent)' : undefined }}>
      <div className="row">
        {can(role, 'propose') && f.status === 'open' && f.proposed.length > 0 && <input type="checkbox" checked={sel.has(f.id)} onChange={e => { const n = new Set(sel); e.target.checked ? n.add(f.id) : n.delete(f.id); setSel(n) }} />}
        <span className="pill-sev" style={{ color: ({ error: 'var(--err)', warning: 'var(--warn)', review: 'var(--rev)' } as Any)[f.severity] }}>{f.severity}</span>
        <b>{f.title}</b><span className="chip">{boot.areas[f.area]}</span><span className="chip">{f.kind.replace(/_/g, ' ')}</span><span className="sp" />
        {(f.est_fed !== 0 || f.est_ca !== 0) && <span className="small">Fed <b className="num">{signed(f.est_fed)}</b> · CA <b className="num">{signed(f.est_ca)}</b></span>}
        <span className={'chip ' + (f.status === 'open' ? 'warn' : 'ok')}>{f.status}</span>
      </div>
      <p style={{ margin: '8px 0' }}>{f.summary}</p>
      {(f.engine_value !== null || f.expected_value !== null) && f.engine_value !== undefined && <div className="small">Engine: <b className="num">{fmtVal(f.engine_value)}</b> → expected: <b className="num">{fmtVal(f.expected_value)}</b></div>}
      <div className="row" style={{ gap: 4, margin: '6px 0' }}><span className="small muted">Evidence:</span>{f.refs.slice(0, 14).map((r: Any, i: number) => <Ref key={i} r={r} />)}{f.refs.length > 14 && <span className="small muted">+{f.refs.length - 14}</span>}</div>
      {f.proposed.length > 0 && <table className="t small" style={{ margin: '6px 0' }}><thead><tr><th>Proposed adjustment</th><th>Line</th><th className="n">Change</th><th>Tax-effect category</th></tr></thead>
        <tbody>{f.proposed.map((p: Any, i: number) => <tr key={i}><td>{p.description}</td><td><Ref r={{ type: 'line', id: p.line }} /></td><td className="n num">{signed(p.delta)}</td><td>{p.category || '—'}</td></tr>)}</tbody></table>}
      {f.how_surfaced && <div className="small muted">How the design surfaces it: {f.how_surfaced}</div>}
      {f.status !== 'open' && <div className="small">Status: {f.status} by {f.status_by} {dt(f.status_ts)} — {f.status_reason}{f.authority && ` (authority: ${f.authority})`}</div>}
      <div className="row" style={{ marginTop: 8 }}>
        {f.status === 'open' && can(role, 'propose') && f.severity !== 'info' && <><button className="btn sm pri" onClick={() => accept([f])}>{f.proposed.length ? 'Accept & propose adjustments' : 'Accept'}</button><button className="btn sm" onClick={() => dismiss(f)}>Dismiss…</button></>}
        {f.status !== 'open' && can(role, 'propose') && <button className="btn sm" onClick={() => send({ type: 'finding.reopened', payload: { id: f.id } }, 'Finding reopened')}>Reopen</button>}
        <NoteBtn target={'finding:' + f.id} />
        {f.adjustments.length > 0 && <button className="btn sm" onClick={() => go('review', 'adjustments')}>{f.adjustments.length} adjustment(s) →</button>}
      </div>
      <FindingNotes id={f.id} />
    </div>)}
    {!list.length && <div className="empty">Nothing here.</div>}
  </div>
}

function NoteBtn({ target }: { target: string }) { const a = useActions(); return <button className="btn sm" onClick={() => a.note(target)}>✎ Note</button> }
function FindingNotes({ id }: { id: string }) {
  const { st } = useApp()
  const ns = st.notes.filter((n: Any) => n.target === 'finding:' + id)
  if (!ns.length) return null
  return <div style={{ marginTop: 6 }}>{ns.map((n: Any) => <div key={n.id} className="small" style={{ borderLeft: n.blocking && n.status === 'open' ? '3px solid var(--err)' : '3px solid var(--line)', paddingLeft: 8, margin: '4px 0' }}><span className="chip">{n.kind.replace(/_/g, ' ')}</span> {n.text} <span className="muted">({n.status})</span></div>)}</div>
}

// ---------------------------------------------------------------- Return lines
export function ReturnPage() {
  const { boot, arg, go, role, send, ask } = useApp()
  const [version, setVersion] = useState('v3')
  const [lines] = useLoad<Any[]>('/api/lines?version=' + version, [version])
  const [q, setQ] = useState('')
  const [onlyChanged, setOnlyChanged] = useState(false)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const forms = useMemo(() => { const m: Record<string, number> = {}; (lines || []).forEach((l: Any) => { m[l.form] = (m[l.form] || 0) + 1 }); return m }, [lines])
  const form = arg || 'F1040'
  if (!lines || !boot) return <div className="empty">Loading…</div>
  const rows = lines.filter((l: Any) => (q ? (l.key + ' ' + l.label).toLowerCase().includes(q.toLowerCase()) : l.form === form) && (!onlyChanged || l.adjusted !== l.value || l.pending !== l.value))
  const shown = rows.slice(0, 400)
  const bulkVerify = async () => {
    const v = await ask({ title: `Verify ${sel.size} lines`, text: 'One batch — one undo.', fields: [{ key: 'vtype', label: 'Verification', type: 'select', options: boot.standards.verification_types }, { key: 'note', label: 'What was checked', type: 'textarea', required: true }] })
    if (!v) return
    await send([...sel].map(k => ({ type: 'verification.added', payload: { target: 'line:' + k, vtype: v.vtype, note: v.note } })), `${sel.size} lines verified`)
    setSel(new Set())
  }
  return <div>
    <h1>Return</h1>
    <p className="sub">Every number opens its trace: how it was built, the exact source field on the page, verification and history.</p>
    <div className="row" style={{ marginBottom: 10 }}>
      <input placeholder="Filter lines across all forms…" value={q} onChange={e => setQ(e.target.value)} style={{ padding: '6px 10px', border: '1px solid var(--line)', borderRadius: 8, width: 300 }} />
      <select value={version} onChange={e => setVersion(e.target.value)} className="btn">{boot.packet.versions.map((v: Any) => <option key={v.version} value={v.version}>{v.version} — {v.computed_at.slice(0, 10)}</option>)}</select>
      <label className="small"><input type="checkbox" checked={onlyChanged} onChange={e => setOnlyChanged(e.target.checked)} /> only adjusted</label>
      <span className="sp" />{sel.size > 0 && can(role, 'verify') && <button className="btn pri" onClick={bulkVerify}>Verify {sel.size} selected</button>}
    </div>
    <div className="split">
      <div className="forms card" style={{ padding: 6, alignSelf: 'start', maxHeight: '75vh', overflow: 'auto' }}>{Object.keys(forms).map(f => <button key={f} className={f === form && !q ? 'on' : ''} onClick={() => { setQ(''); go('return', f) }}>{boot.forms[f] || f} <span className="muted small">{forms[f]}</span></button>)}</div>
      <div className="card" style={{ padding: 0, overflow: 'auto', maxHeight: '78vh' }}>
        <table className="t"><thead><tr><th><input type="checkbox" onChange={e => setSel(e.target.checked ? new Set(shown.map((l: Any) => l.key)) : new Set())} /></th><th>Line</th><th>Label</th><th className="n">Engine</th><th className="n">Workpaper</th><th>Status</th></tr></thead>
          <tbody>{shown.map((l: Any) => <tr key={l.key}>
            <td><input type="checkbox" checked={sel.has(l.key)} onChange={e => { const n = new Set(sel); e.target.checked ? n.add(l.key) : n.delete(l.key); setSel(n) }} /></td>
            <td className="num small">{l.key}</td><td>{l.label}{l.note && <div className="small muted">{l.note.slice(0, 110)}</div>}</td>
            <td className="n"><Num k={l.key} v={l.value} /></td><td className="n">{l.adjusted !== l.value || l.pending !== l.value ? <Num k={l.key} v={l.value} adj={l.pending} /> : <span className="muted">=</span>}</td>
            <td>{l.verified.length > 0 && <span className="chip ok">✓</span>} {l.adjustments > 0 && <span className="chip warn">± {l.adjustments}</span>} {l.open_notes > 0 && <span className="chip rev">✎ {l.open_notes}</span>} {!l.has_sources && !l.inputs.length && <span className="chip" title="no source or inputs">no source</span>}</td>
          </tr>)}</tbody></table>
        {rows.length > shown.length && <div className="empty">{rows.length - shown.length} more — narrow the filter (sales detail lives under Schedules → Sales).</div>}
      </div>
    </div>
  </div>
}

// ---------------------------------------------------------------- Documents
export function Documents() {
  const { arg, go, boot } = useApp()
  const [docs] = useLoad<Any[]>('/api/documents')
  const [f, setF] = useState('all')
  if (!docs || !boot) return <div className="empty">Loading…</div>
  if (arg) return <div><button className="btn sm" onClick={() => go('documents')}>← Document index</button><div className="card" style={{ marginTop: 10 }}><DocView id={arg} /></div></div>
  const counts = docs.reduce((m: Any, d: Any) => ({ ...m, [d.status]: (m[d.status] || 0) + 1 }), {})
  const list = docs.filter(d => f === 'all' || d.status === f || (f === 'flagged' && (d.findings.length || d.low_confidence.length)))
  return <div>
    <h1>Document index</h1>
    <p className="sub">Every document either lands on the return or says why not. "Not applied" = the engine marked it used but no number moved.</p>
    <div className="tabs">{[['all', docs.length], ['landed', counts.landed], ['not_applied', counts.not_applied], ['explained', counts.explained], ['unaccounted', counts.unaccounted || 0], ['flagged', docs.filter(d => d.findings.length || d.low_confidence.length).length]].map(([k, n]) => <button key={k} className={f === k ? 'on' : ''} onClick={() => setF(k as string)}>{String(k).replace('_', ' ')} <span className="muted small">{n}</span></button>)}</div>
    <table className="t card"><thead><tr><th>ID</th><th>Document</th><th>Received</th><th>Area</th><th>Status</th><th className="n">Values</th><th>Landed on</th><th>Flags</th></tr></thead>
      <tbody>{list.map(d => <tr key={d.id} className="click" onClick={() => go('documents', d.id)}>
        <td className="num">{d.id}</td><td>{d.title}<div className="small muted">{d.issuer} · {d.belongs_to} · TY{d.tax_year}</div></td><td className="small num">{d.received_at.slice(0, 10)}</td>
        <td className="small">{boot.areas[d.area]}</td>
        <td><span className={'chip ' + ({ landed: 'ok', explained: '', not_applied: 'err', unaccounted: 'warn' } as Any)[d.status]}>{d.status.replace('_', ' ')}</span>{d.corrected && <span className="chip warn">corrected</span>}{d.superseded_in.length > 0 && <span className="chip">superseded</span>}</td>
        <td className="n num">{d.values}</td><td className="small">{d.landed_count ? `${d.landed_count} lines` : <span className="muted">{(d.disposition || '').slice(0, 60)}</span>}</td>
        <td>{d.extraction.status !== 'extracted' && <span className="chip warn">{d.extraction.status}</span>}{d.findings.length > 0 && <span className="chip err">⚑ {d.findings.length}</span>}{d.low_confidence.length > 0 && <span className="chip warn">{d.low_confidence.length} low conf.</span>}{d.verified.length > 0 && <span className="chip ok">✓</span>}</td></tr>)}</tbody></table>
  </div>
}
