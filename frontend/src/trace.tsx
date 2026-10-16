import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Any, Ref, Sev, api, can, day, dt, fmtVal, money, registerTrace, signed, useApp, useLoad } from './lib'

export const CATEGORIES = ['interest', 'stcg', 'ltcg', 'schc_profit', 'schc_expense', 'ordinary_income', 'wages', 'adjustment', 'salt', 'itemized', 'ca_source_income', 'payment_fed', 'payment_ca', 'credit_fed', '(no tax effect)']

export function useActions() {
  const app = useApp()
  const { send, ask, boot, st } = app
  const vtypes: string[] = st?.standards?.verification_types || boot?.standards?.verification_types || []
  return {
    verify: async (target: string, label: string) => {
      const v = await ask({ title: 'Record verification', text: label, fields: [{ key: 'vtype', label: 'How was it verified?', type: 'select', options: vtypes }, { key: 'note', label: 'What you checked (evidence)', type: 'textarea', required: true }] })
      if (v) await send({ type: 'verification.added', payload: { target, vtype: v.vtype, note: v.note } }, 'Verification recorded')
    },
    propose: async (line: string, base?: Any, finding?: string) => {
      const v = await ask({ title: `Adjust ${line}`, text: base !== undefined ? `Engine value ${fmtVal(base)}. Enter the change (not the new value). The original stays on record.` : undefined, fields: [
        { key: 'delta', label: 'Change (+/-)', type: 'number', required: true }, { key: 'category', label: 'Tax-effect category', type: 'select', options: CATEGORIES },
        { key: 'description', label: 'Short description', required: true }, { key: 'reason', label: 'Why (evidence, authority)', type: 'textarea', required: true }] })
      if (v) await send({ type: 'adjustment.proposed', payload: { line, delta: Number(v.delta), category: v.category === '(no tax effect)' ? null : v.category, description: v.description, reason: v.reason, finding } }, 'Adjustment proposed')
    },
    note: async (target: string, kinds?: string[]) => {
      const role = app.role
      const all = ['preparer_note', 'review_note', 'judgment', 'election', 'due_diligence', 'penalty_decision', 'variance_explanation', 'comment', 'post_filing']
      const allowed = (kinds || all).filter(k => k === 'comment' || (k === 'review_note' ? can(role, 'review_note') : k === 'penalty_decision' ? ['reviewer', 'partner'].includes(role) : k === 'post_filing' ? ['quality_reviewer', 'partner', 'reviewer', 'preparer'].includes(role) : can(role, 'judgment')))
      const v = await ask({ title: 'Add note', fields: [{ key: 'kind', label: 'Kind', type: 'select', options: allowed }, { key: 'text', label: 'Note', type: 'textarea', required: true },
        { key: 'authority', label: 'Authority relied on (required for judgments, elections, penalty decisions)' }, { key: 'blocking', label: 'Blocks filing? (review notes)', type: 'select', options: ['yes', 'no'] }] })
      if (v) await send({ type: 'note.created', payload: { target, kind: v.kind, text: v.text, authority: v.authority || null, blocking: v.kind === 'review_note' && v.blocking === 'yes' } }, 'Note added')
    },
    question: async (target: string) => {
      const people = (boot?.people || []).filter((p: Any) => p.kind === 'staff').map((p: Any) => `${p.id} ${p.name}`)
      const v = await ask({ title: 'Ask a question', text: 'The answer is stored as evidence on this item.', fields: [{ key: 'to', label: 'To', type: 'select', options: ['client', ...people] }, { key: 'text', label: 'Question', type: 'textarea', required: true }] })
      if (v) await send({ type: 'question.asked', payload: { target, to: v.to === 'client' ? 'client' : v.to.split(' ')[0], text: v.text } }, 'Question sent')
    },
    attach: async (target: string) => {
      const inp = document.createElement('input'); inp.type = 'file'
      inp.onchange = async () => {
        const f = inp.files?.[0]; if (!f) return
        const fd = new FormData(); fd.append('file', f); fd.append('target', target)
        await api('/api/files', { method: 'POST', body: fd }); await app.refresh(); app.toast('File attached as evidence')
      }
      inp.click()
    },
    link: async (from: string) => {
      const v = await ask({ title: 'Link related item', text: 'e.g. line:SchD.12, doc:D37, py:/return_2024/K1_1065, or a related return', fields: [{ key: 'to', label: 'Related item', required: true }, { key: 'why', label: 'Relationship' }] })
      if (v) await send({ type: 'link.added', payload: { from, to: v.to, why: v.why } }, 'Link added')
    },
  }
}

function Actions({ target, line, base }: { target: string; line?: string; base?: Any }) {
  const { role, st } = useApp()
  const a = useActions()
  const frozen = st?.filing?.frozen_at && ['submitted', 'filed'].includes(st?.filing?.status)
  return <div className="row" style={{ margin: '8px 0 4px' }}>
    {can(role, 'verify') && !frozen && <button className="btn sm" onClick={() => a.verify(target, target)}>✓ Verify</button>}
    {line && can(role, 'propose') && !frozen && <button className="btn sm" onClick={() => a.propose(line, base)}>± Adjust</button>}
    <button className="btn sm" onClick={() => a.note(target)}>✎ Note</button>
    {can(role, 'ask') && <button className="btn sm" onClick={() => a.question(target)}>? Ask</button>}
    <button className="btn sm" onClick={() => a.attach(target)}>⇪ Attach</button>
    <button className="btn sm" onClick={() => a.link(target)}>⛓ Link</button>
  </div>
}

function Tree({ n, depth = 0 }: { n: Any; depth?: number }) {
  const { trace } = useApp()
  const [open, setOpen] = useState(depth < 1)
  if (n.missing) return <div className="node muted">{n.key} (not in this version)</div>
  const changed = typeof n.value === 'number' && typeof n.adjusted === 'number' && Math.abs(n.value - n.adjusted) > 0.004
  return <div className="node">
    <div className="row" style={{ gap: 6 }}>
      {n.children?.length ? <button className="chip" onClick={() => setOpen(!open)}>{open ? '−' : '+'}</button> : <span style={{ width: 22 }} />}
      <a onClick={() => trace({ kind: 'line', id: n.key })} style={{ cursor: 'pointer' }}><b>{n.key}</b></a>
      <span className="muted small" style={{ maxWidth: 330, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.label}</span>
      <span className="sp" />
      <span className="num">{changed ? <><span className="strike">{fmtVal(n.value)}</span> {fmtVal(n.adjusted)}</> : fmtVal(n.value)}</span>
      <span className="chip" title="engine rule">{n.rule}</span>
    </div>
    {n.sources?.length > 0 && <div className="row" style={{ marginLeft: 28, gap: 4 }}>{n.sources.slice(0, 6).map((s: Any) => <Ref key={s.id} r={{ type: s.type === 'ev' ? 'ev' : s.type, id: s.id, doc: s.doc, page: s.page }}>{s.type === 'ev' ? `${s.doc} p${s.page} · ${s.label}` : s.id}</Ref>)}{n.sources.length > 6 && <span className="muted small">+{n.sources.length - 6}</span>}</div>}
    {open && n.children?.length > 0 && <div className="kids">{n.children.map((c: Any, i: number) => <Tree key={c.key + i} n={c} depth={depth + 1} />)}</div>}
    {n.more && <div className="muted small" style={{ marginLeft: 28 }}>… {n.more} more inputs (open {n.key})</div>}
  </div>
}

function LineTrace({ id }: { id: string }) {
  const { st, name, send, role, trace, go } = useApp()
  const [d] = useLoad<Any>('/api/line/' + encodeURIComponent(id), [id])
  if (!d) return <div className="empty">Loading…</div>
  const pending = d.pending !== d.adjusted
  return <div>
    <div className="muted small">{d.form_name} · line {d.line} · {d.jurisdiction} · area {d.area}</div>
    <h1 style={{ fontSize: 18 }}>{d.label}</h1>
    <div className="grid g3" style={{ margin: '10px 0' }}>
      <div className="card kpi"><div className="lbl">Engine ({st?.filing ? 'v3' : ''})</div><div className="val">{fmtVal(d.value)}</div></div>
      <div className="card kpi"><div className="lbl">Workpaper (approved)</div><div className="val">{fmtVal(d.adjusted)}</div></div>
      <div className="card kpi"><div className="lbl">Incl. pending</div><div className="val">{fmtVal(d.pending)}</div>{pending && <div className="delta muted">awaiting approval</div>}</div>
    </div>
    <div className="row">{d.verified.map((v: string, i: number) => <span key={i} className="chip ok">✓ {v.replace(/_/g, ' ')}</span>)}{!d.verified.length && <span className="chip">not verified</span>}
      {d.findings.map((f: Any) => <button key={f.id} className={'chip ' + (f.status === 'open' ? ({ error: 'err', warning: 'warn', review: 'rev' } as Any)[f.severity] || '' : 'ok')} onClick={() => go('findings', f.id)}>⚑ {f.title.slice(0, 48)}</button>)}</div>
    <Actions target={'line:' + id} line={id} base={d.value} />
    <p className="small"><b>Rule {d.rule}.</b> {d.rule_text}{d.note && <><br /><span className="muted">Engine note: {d.note}</span></>}</p>

    <h3>How this number was built</h3>
    <div className="tree card"><Tree n={d.tree} /></div>

    {d.sources.length > 0 && <><h3>Sources ({d.sources.length})</h3>
      <table className="t"><tbody>{d.sources.slice(0, 40).map((s: Any) => <tr key={s.id} className="click" onClick={() => s.type === 'ev' ? trace({ kind: 'doc', id: s.doc, page: s.page, ev: s.id }) : trace({ kind: 'evidence', ref: { type: s.type, id: s.id } })}>
        <td>{s.type === 'ev' ? <><b>{s.doc}</b> p{s.page}</> : s.type}</td><td>{s.label}<div className="muted small">{s.type === 'ev' ? `${s.doc_title} · field ${s.field}` : s.id}</div></td>
        <td className="n">{fmtVal(s.value)}</td><td>{s.type === 'ev' && <span className={'chip ' + (s.confidence < 0.9 ? 'warn' : '')}>{Math.round(s.confidence * 100)}%</span>}{s.type === 'ev' && s.text_as_read === '' && <span className="chip err">blank on page</span>}</td></tr>)}</tbody></table></>}

    <h3>Across versions and years</h3>
    <table className="t"><thead><tr>{Object.keys(d.versions).map(v => <th key={v} className="n">{v}</th>)}<th className="n">Workpaper</th><th className="n">2024 filed</th></tr></thead>
      <tbody><tr>{Object.values(d.versions).map((v: Any, i) => <td key={i} className="n num">{fmtVal(v)}</td>)}<td className="n num">{fmtVal(d.adjusted)}</td><td className="n num">{fmtVal(d.prior_year.value)}</td></tr></tbody></table>
    {d.dependents.length > 0 && <p className="small">Feeds: {d.dependents.map((k: string) => <Ref key={k} r={{ type: 'line', id: k }} />)}</p>}
    {(d.related.length > 0 || d.links.length > 0) && <><h3>Related</h3>{d.related.map((r: Any, i: number) => <div key={i} className="small">↔ {r.label} <span className="muted">({r.ref})</span></div>)}
      {d.links.map((l: Any, i: number) => <div key={'l' + i} className="small">⛓ {l.from === 'line:' + id ? l.to : l.from} — {l.why} <span className="muted">({name(l.by)})</span></div>)}</>}

    <h3>Adjustments</h3>
    {d.adjustments_list.length === 0 ? <div className="muted small">None — engine value stands.</div> : d.adjustments_list.map((a: Any) => <AdjCard key={a.id} a={a} />)}

    <h3>Verification, notes, questions, files</h3>
    {d.verifications.map((v: Any) => <div key={v.id} className="small" style={{ margin: '4px 0' }}><span className={'chip ' + (v.active ? 'ok' : '')}>✓ {v.vtype.replace(/_/g, ' ')}</span> {v.note} <span className="muted">— {name(v.by)}, {dt(v.ts)}</span>
      {v.active && can(role, 'verify') && <button className="btn sm" style={{ marginLeft: 6 }} onClick={() => send({ type: 'verification.removed', payload: { id: v.id } }, 'Verification withdrawn')}>withdraw</button>}</div>)}
    {d.notes.map((n: Any) => <NoteCard key={n.id} n={n} />)}
    {d.questions.map((q: Any) => <QuestionCard key={q.id} q={q} />)}
    {d.files.map((f: Any) => <div key={f.id} className="small">📎 <a href={'/api/files/' + f.id} target="_blank">{f.name}</a> <span className="muted">{name(f.by)} {dt(f.ts)}</span></div>)}
  </div>
}

export function AdjCard({ a }: { a: Any }) {
  const { name, role, send, person } = useApp()
  return <div className="card" style={{ margin: '6px 0', padding: '10px 12px' }}>
    <div className="row"><b>{a.line}</b><span className="num">{signed(a.delta)}</span><span className={'chip ' + (a.status === 'approved' ? 'ok' : a.status === 'reversed' ? '' : 'warn')}>{a.status}</span>
      {a.requires_partner && <span className="chip rev">partner sign-off (&gt;1,000 effect)</span>}<span className="sp" />
      <span className="small">Fed <b className="num">{signed(a.fed_effect + a.fed_balance)}</b> · CA <b className="num">{signed(a.ca_effect + a.ca_balance)}</b></span></div>
    <div className="small">{a.description}</div>
    <div className="small muted">Why: {a.reason}</div>
    <div className="small muted">Proposed by {name(a.proposed_by)} {dt(a.ts)}{a.approvals.map((x: Any, i: number) => <span key={i}> · approved by {name(x.by)} ({x.role}) {dt(x.ts)}</span>)}{a.status === 'reversed' && <> · reversed by {name(a.reversed_by)}: {a.reverse_reason}</>}</div>
    <div className="row" style={{ marginTop: 4 }}>
      {a.status === 'proposed' && can(role, 'approve') && a.proposed_by !== person && <button className="btn sm pri" onClick={() => send({ type: 'adjustment.approved', payload: { id: a.id } }, a.requires_partner && role !== 'partner' ? 'Reviewer approval recorded — partner still required' : 'Adjustment approved')}>Approve</button>}
      {a.status !== 'reversed' && can(role, 'propose') && <button className="btn sm" onClick={async () => { await send({ type: 'adjustment.reversed', payload: { id: a.id, reason: 'Reversed from trace' } }, 'Adjustment reversed (original kept)') }}>Reverse</button>}
    </div>
  </div>
}

export function NoteCard({ n }: { n: Any }) {
  const { name, send, ask, role } = useApp()
  return <div className="card" style={{ margin: '6px 0', padding: '10px 12px', borderLeft: n.blocking && n.status === 'open' ? '3px solid var(--err)' : undefined }}>
    <div className="row"><span className={'chip ' + (n.kind === 'review_note' ? 'rev' : n.kind === 'judgment' || n.kind === 'election' ? 'acc' : '')}>{n.kind.replace(/_/g, ' ')}</span>
      {n.blocking && <span className="chip err">blocks filing</span>}<span className={'chip ' + (n.status === 'open' ? 'warn' : 'ok')}>{n.status}</span><span className="sp" /><span className="muted small">{name(n.by)} · {dt(n.ts)}</span></div>
    <div style={{ margin: '6px 0' }}>{n.text}</div>
    {n.authority && <div className="small"><b>Authority:</b> {n.authority}</div>}
    {n.replies.map((r: Any, i: number) => <div key={i} className="small" style={{ marginLeft: 12 }}>↳ {r.text} <span className="muted">— {name(r.by)} {dt(r.ts)}</span></div>)}
    {n.resolution && <div className="small" style={{ marginLeft: 12 }}>✔ {n.resolution} <span className="muted">— {name(n.resolved_by)}</span></div>}
    <div className="row" style={{ marginTop: 4 }}>
      <button className="btn sm" onClick={async () => { const v = await ask({ title: 'Reply', fields: [{ key: 'text', label: 'Reply', type: 'textarea', required: true }] }); if (v) send({ type: 'note.replied', payload: { id: n.id, text: v.text } }, 'Reply added') }}>Reply</button>
      {n.status === 'open' && role !== 'client' && <button className="btn sm" onClick={async () => { const v = await ask({ title: 'Resolve note', fields: [{ key: 'text', label: 'Resolution', type: 'textarea', required: true }] }); if (v) send({ type: 'note.resolved', payload: { id: n.id, text: v.text } }, 'Note resolved') }}>Resolve</button>}
      {n.status === 'resolved' && <button className="btn sm" onClick={() => send({ type: 'note.reopened', payload: { id: n.id } }, 'Note reopened')}>Reopen</button>}
    </div>
  </div>
}

export function QuestionCard({ q }: { q: Any }) {
  const { name, send, ask, person, role } = useApp()
  const mine = q.to === person || (q.to === 'client' && role === 'client')
  return <div className="card" style={{ margin: '6px 0', padding: '10px 12px' }}>
    <div className="row"><span className="chip rev">question</span><span className={'chip ' + (q.status === 'open' ? 'warn' : 'ok')}>{q.status}</span><span className="small muted">{name(q.by)} → {q.to === 'client' ? 'Client' : name(q.to)} · {dt(q.ts)}</span><span className="sp" />{q.target && <span className="small muted">{q.target}</span>}</div>
    <div style={{ margin: '6px 0' }}>{q.text}</div>
    {q.answers.map((a: Any, i: number) => <div key={i} className="small" style={{ marginLeft: 12 }}>↳ <b>{a.text}</b> <span className="muted">— {name(a.by)} {dt(a.ts)} (kept as evidence)</span></div>)}
    {mine && q.status === 'open' && <button className="btn sm pri" onClick={async () => { const v = await ask({ title: 'Answer', fields: [{ key: 'text', label: 'Your answer', type: 'textarea', required: true }] }); if (v) send({ type: 'question.answered', payload: { id: q.id, text: v.text } }, 'Answer sent') }}>Answer</button>}
  </div>
}

// ---------------------------------------------------------------- documents
export function DocView({ id, page, ev, compact }: { id: string; page?: number; ev?: string; compact?: boolean }) {
  const { trace, name } = useApp()
  const [d] = useLoad<Any>('/api/documents/' + id, [id])
  const [pg, setPg] = useState<number>(page || 1)
  const [focus, setFocus] = useState<string | undefined>(ev)
  const pageRef = useRef<HTMLDivElement>(null)
  useEffect(() => { setPg(page || 1); setFocus(ev) }, [id, page, ev])
  useEffect(() => { const m = pageRef.current?.querySelector('mark.focus'); m?.scrollIntoView({ block: 'center' }) }, [d, pg, focus])
  const values = useMemo(() => Object.fromEntries((d?.values_detail || []).map((v: Any) => [v.id, v])), [d])
  if (!d) return <div className="empty">Loading document…</div>
  const P = d.pages_detail.find((x: Any) => x.page === pg) || d.pages_detail[0]
  const text: string = P.render.content
  const anchors = P.anchors.filter((a: Any) => a.start !== null).sort((a: Any, b: Any) => a.start - b.start)
  const parts: React.ReactNode[] = []
  let cur = 0
  anchors.forEach((a: Any, i: number) => {
    if (a.start < cur) return
    parts.push(text.slice(cur, a.start))
    const v = values[a.ev]
    const bad = v && (v.text_as_read === '' || v.confidence < 0.9)
    parts.push(<mark key={i} className={(a.ev === focus ? 'focus ' : '') + (bad ? 'bad' : '')} title={`${a.ev} · ${v?.label} = ${fmtVal(v?.value)} · confidence ${v?.confidence}`} onClick={() => setFocus(a.ev)}>{text.slice(a.start, a.end)}</mark>)
    cur = a.end
  })
  parts.push(text.slice(cur))
  const fv = focus ? values[focus] : null
  const unanchored = P.anchors.filter((a: Any) => a.start === null && !a.implied).map((a: Any) => values[a.ev])
  const implied = P.anchors.filter((a: Any) => a.implied).length
  return <div>
    <div className="row"><b>{d.id}</b><span>{d.title}</span></div>
    <div className="small muted">{d.issuer} · received {dt(d.received_at)} by {d.uploaded_by} · {d.file_name} · extraction {d.extraction.status}{d.extraction.reason ? ` — ${d.extraction.reason}` : ''}</div>
    <div className="row" style={{ margin: '6px 0' }}>
      <span className={'chip ' + ({ landed: 'ok', explained: '', not_applied: 'err', unaccounted: 'warn' } as Any)[d.status]}>{d.status.replace('_', ' ')}</span>
      {d.corrected && <span className="chip warn">CORRECTED</span>}{d.superseded_in.length > 0 && <span className="chip">superseded in {d.superseded_in.join(', ')}</span>}
      {d.verified.map((v: string, i: number) => <span key={i} className="chip ok">✓ {v.replace(/_/g, ' ')}</span>)}
      {d.low_confidence.length > 0 && <span className="chip warn">{d.low_confidence.length} low-confidence reads</span>}
    </div>
    {!compact && <Actions target={'doc:' + d.id} />}
    <div className="small" style={{ margin: '4px 0 8px' }}><b>Landed on:</b> {d.landed_lines.length ? d.landed_lines.slice(0, 30).map((k: string) => <Ref key={k} r={{ type: 'line', id: k }} />) : <span className="muted">{d.disposition || 'nowhere'}</span>}{d.landed_lines.length > 30 && <span className="muted"> +{d.landed_lines.length - 30}</span>}</div>
    {d.pages_detail.length > 1 && <div className="row" style={{ gap: 4, marginBottom: 6 }}>{d.pages_detail.map((x: Any) => <button key={x.page} className={'chip ' + (x.page === pg ? 'acc' : '')} onClick={() => { setPg(x.page); setFocus(undefined) }}>p{x.page}{x.anchors.length ? ` · ${x.anchors.length}` : ''}</button>)}</div>}
    <div className="small muted" style={{ marginBottom: 4 }}>Simulated page (rendered from printed_content). Highlights are the pipeline's extracted fields; a real page image plugs into the same anchors as bounding boxes.</div>
    <div className="page" ref={pageRef}>{parts}</div>
    {fv && <div className="card" style={{ marginTop: 10 }}>
      <div className="row"><b>{fv.id}</b><span>{fv.label}</span><span className="sp" /><span className={'chip ' + (fv.confidence < 0.9 ? 'warn' : '')}>confidence {fv.confidence}</span></div>
      <div className="fld" style={{ marginTop: 6 }}><div>Field</div><div>{fv.field} ({fv.value_type})</div><div>Extracted value</div><div className="num">{fmtVal(fv.value)}</div><div>Text as read</div><div className="num">{fv.text_as_read === '' ? <span className="chip err">nothing printed — blank</span> : fv.text_as_read}</div>
        <div>Position</div><div className="small muted">x {fv.position.x0}–{fv.position.x1}, y {fv.position.y0}–{fv.position.y1}</div><div>Landed on</div><div>{fv.landed.length ? fv.landed.map((k: string) => <Ref key={k} r={{ type: 'line', id: k }} />) : <span className="muted">no return line uses this value</span>}</div></div>
      <Actions target={'ev:' + fv.id} />
    </div>}
    {implied > 0 && <div className="small muted" style={{ marginTop: 6 }}>{implied} implied values (covered flags, zero wash sales) are not printed as text.</div>}
    {unanchored.length > 0 && <div className="small muted" style={{ marginTop: 6 }}>Extracted values that do not appear on this page: {unanchored.map((v: Any) => <span key={v.id} className="chip err" style={{ marginRight: 4 }}>{v.id} {v.label}: {fmtVal(v.value)}</span>)}</div>}
    {!compact && d.notes.length > 0 && <><h3>Notes</h3>{d.notes.map((n: Any) => <NoteCard key={n.id} n={n} />)}</>}
    {!compact && d.files.length > 0 && <><h3>Attached</h3>{d.files.map((f: Any) => <div key={f.id} className="small">📎 <a href={'/api/files/' + f.id} target="_blank">{f.name}</a> {name(f.by)}</div>)}</>}
  </div>
}

function EvidenceView({ r }: { r: Any }) {
  const { boot } = useApp()
  if (!boot) return null
  let body: React.ReactNode = <pre className="page">{JSON.stringify(r, null, 2)}</pre>
  if (r.type === 'qa') { const q = boot.client.questionnaire.find((x: Any) => x.id === r.id); body = q && <div className="card"><div className="muted small">Questionnaire {q.id} · {q.answered_by} · {dt(q.answered_at)}</div><p><b>{q.question}</b></p><p>{q.answer}</p></div> }
  if (r.type === 'msg') { const q = boot.client.messages.find((x: Any) => x.id === r.id); body = q && <div className="card"><div className="muted small">Message {q.id} · {q.from} → {q.to} · {dt(q.sent_at)}</div><p>{q.text}</p></div> }
  if (r.type === 'call') { const c = boot.client.call_notes[0]; body = <div className="card"><div className="muted small">Call {c.id} · {dt(c.date)} · {c.participants.join(', ')}</div><ul>{c.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul></div> }
  if (r.type === 'agency') { const parts = r.id.split('/').filter(Boolean); let cur: Any = boot.agency; for (const p of parts) cur = cur?.[isNaN(+p) ? p : +p]; body = <pre className="page">{JSON.stringify(cur, null, 2)}</pre> }
  if (r.type === 'whatif') { const w = boot.what_if.alternatives.find((x: Any) => x.id === r.id); body = w && <div className="card"><p><b>{w.description}</b></p><p>Federal total tax change <b className="num">{signed(w.federal.total_tax_change)}</b>, California <b className="num">{signed(w.california.total_tax_change)}</b> (engine-computed alternative on {w.base_version}).</p></div> }
  return <div><div className="muted small">{r.type} · {r.id}</div>{body}<Actions target={`${r.type}:${r.id}`} /></div>
}

function Trace({ t, close }: Any) {
  return <>
    <div className="hd"><b>{t.kind === 'line' ? 'Trace a number' : t.kind === 'doc' ? 'Source document' : 'Evidence'}</b><span className="sp" /><span className="kbd">Esc</span><button className="btn sm" onClick={close}>Close</button></div>
    <div className="bd">{t.kind === 'line' ? <LineTrace id={t.id} /> : t.kind === 'doc' ? <DocView id={t.id} page={t.page} ev={t.ev} /> : <EvidenceView r={t.ref} />}</div>
  </>
}
registerTrace(function TraceWrap(p: Any) {
  useEffect(() => { const on = (e: KeyboardEvent) => e.key === 'Escape' && p.close(); window.addEventListener('keydown', on); return () => window.removeEventListener('keydown', on) }, [])
  return <Trace {...p} />
})
