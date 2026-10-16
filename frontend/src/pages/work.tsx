import React, { useMemo, useState } from 'react'
import { AREA_ORDER, Any, Num, Ref, api, can, day, dt, fmtVal, money, post, signed, useApp, useLoad } from '../lib'
import { AdjCard, CATEGORIES, CATEGORY_LABEL, NoteCard, QuestionCard, useActions } from '../trace'
import { openAsk } from '../ask'

// ---------------------------------------------------------------- Review
export function Review() {
  const { st, boot, arg, go, send, role, name, person, ask } = useApp()
  if (!st || !boot) return null
  const tab = ['notes', 'signoffs', 'adjustments', 'batches'].includes(arg) ? arg : AREA_ORDER.includes(arg) ? 'signoffs' : 'notes'
  const sign = async (area: string, level: string) => {
    await send({ type: 'signoff.signed', payload: { area, level } }, `${level} sign-off recorded — it reopens automatically if anything it covers changes`)
  }
  const pendingForMe = st.adjustments.filter((a: Any) => a.status === 'proposed')
  return <div>
    <h1>Review</h1>
    <p className="sub">Review notes block filing until cleared. Sign-offs are pinned to a hash of what was signed (numbers, evidence, finding dispositions) and reopen when it changes. Nobody reviews their own work.</p>
    <div className="tabs">{[['notes', `Notes (${st.notes.filter((n: Any) => n.status === 'open').length} open)`], ['signoffs', 'Sign-offs'], ['adjustments', `Adjustments (${pendingForMe.length} pending)`], ['batches', 'Bulk actions & undo']].map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => go('review', k)}>{l}</button>)}</div>
    {tab === 'notes' && <div>{st.notes.length === 0 && <div className="empty">No notes yet.</div>}
      {[...st.notes].sort((a: Any, b: Any) => (a.status === 'open' ? 0 : 1) - (b.status === 'open' ? 0 : 1) || (b.blocking ? 1 : 0) - (a.blocking ? 1 : 0)).map((n: Any) => <div key={n.id}><div className="small muted" style={{ marginTop: 8 }}>on {n.target.startsWith('line:') ? <Ref r={{ type: 'line', id: n.target.slice(5) }} /> : n.target}</div><NoteCard n={n} /></div>)}</div>}
    {tab === 'signoffs' && <table className="t card"><thead><tr><th>Area</th>{['preparer', 'reviewer', 'partner'].map(l => <th key={l}>{l}</th>)}<th>Content hash</th></tr></thead><tbody>
      {[...AREA_ORDER.filter(a => a !== 'return_summary'), 'return'].map(a => <tr key={a} style={{ background: a === arg ? 'var(--accent-2)' : undefined }}><td>{a === 'return' ? <b>Whole return</b> : boot.areas[a]}</td>
        {['preparer', 'reviewer', 'partner'].map(l => {
          if (a === 'return' && l !== 'partner') return <td key={l} className="muted small">—</td>
          if (a !== 'return' && l === 'partner') return <td key={l} className="muted small">via whole return</td>
          const x = [...st.signoffs].reverse().find((s: Any) => s.area === a && s.level === l)
          return <td key={l}>{x ? <span className={'chip ' + (x.valid ? 'ok' : 'err')} title={`signed hash ${x.hash}, now ${x.current_hash}`}>{x.valid ? '✓' : '↺ reopened'} {name(x.by)} · {day(x.ts)}</span> : <span className="chip">open</span>}
            {role === l && (!x || !x.valid) && <button className="btn sm" style={{ marginLeft: 6 }} onClick={() => sign(a, l)}>Sign</button>}</td>
        })}<td className="small num muted">{a === 'return' ? st.return_hash : st.area_hashes[a]}</td></tr>)}</tbody></table>}
    {tab === 'adjustments' && <div>{st.adjustments.length === 0 && <div className="empty">No adjustments.</div>}{[...st.adjustments].sort((a: Any, b: Any) => (a.status === 'proposed' ? 0 : 1) - (b.status === 'proposed' ? 0 : 1)).map((a: Any) => <AdjCard key={a.id} a={a} />)}</div>}
    {tab === 'batches' && <div><p className="small muted">Every multi-item action is one batch. Undo is an event too — nothing is deleted, and redo is possible.</p>
      <table className="t card"><thead><tr><th>When</th><th>Who</th><th>What</th><th className="n">Items</th><th></th></tr></thead><tbody>
        {st.batches.map((b: Any) => <tr key={b.batch}><td className="small num">{dt(b.ts)}</td><td>{name(b.actor)}</td><td className="small">{b.types.join(', ')}</td><td className="n num">{b.count}</td>
          <td>{can(role, 'propose') && (b.undone ? <><span className="chip">undone</span> <button className="btn sm" onClick={() => send({ type: 'batch.redo', payload: { batch: b.batch } }, 'Redone')}>Redo</button></> : <button className="btn sm" onClick={() => send({ type: 'batch.undo', payload: { batch: b.batch } }, 'Undone')}>Undo</button>)}</td></tr>)}</tbody></table></div>}
  </div>
}

// ---------------------------------------------------------------- People
export function People() {
  const { st, boot, name, send, role, ask, person } = useApp()
  const a = useActions()
  if (!st || !boot) return null
  const staff = boot.people.filter((p: Any) => p.kind === 'staff')
  return <div>
    <h1>People</h1>
    <p className="sub">Questions to the client or colleagues become evidence on the item they're about. Assignments, deadlines and time against budget.</p>
    <div className="grid g2">
      <div><div className="row"><h2>Questions</h2><span className="sp" />{can(role, 'ask') && <button className="btn sm" onClick={() => a.question('area:return_summary')}>Ask…</button>}</div>
        {st.questions.length === 0 && <div className="empty">No questions yet.</div>}{[...st.questions].reverse().map((q: Any) => <QuestionCard key={q.id} q={q} />)}
        <h2>Client's own words (organizer, messages, call)</h2>
        <div className="card small" style={{ maxHeight: 360, overflow: 'auto' }}>{boot.client.messages.map((m: Any) => <div key={m.id} style={{ margin: '6px 0' }}><Ref r={{ type: 'msg', id: m.id }} /> <span className="muted">{dt(m.sent_at)} {m.from}:</span> {m.text}</div>)}</div></div>
      <div><h2>Team</h2>
        <table className="t card"><thead><tr><th>Person</th><th>Role</th><th>Clearance</th><th>Active from</th></tr></thead><tbody>
          {staff.map((p: Any) => <tr key={p.id}><td>{p.name}{p.credential ? `, ${p.credential}` : ''}{Object.entries(st.assignment).filter(([, v]) => v === p.id).map(([k]) => <span key={k} className="chip acc" style={{ marginLeft: 4 }}>{k}</span>)}</td><td>{p.role.replace('_', ' ')}</td>
            <td>{p.sensitive_data_clearance ? <span className="chip ok">cleared</span> : <span className="chip err">masked</span>}{p.note && <div className="small muted">{p.note}</div>}</td><td className="small num">{p.active_from}</td></tr>)}</tbody></table>
        {can(role, 'admin') && <div className="row" style={{ marginTop: 8 }}><button className="btn sm" onClick={async () => {
          const v = await ask({ title: 'Assign work', fields: [{ key: 'area', label: 'Area', type: 'select', options: AREA_ORDER }, { key: 'person', label: 'Person', type: 'select', options: staff.map((p: Any) => `${p.id} ${p.name}`) }] })
          if (v) send({ type: 'assignment.set', payload: { area: v.area, person: v.person.split(' ')[0] } }, 'Assigned')
        }}>Assign an area…</button></div>}
        {Object.keys(st.area_assignee).length > 0 && <div className="small" style={{ marginTop: 6 }}>{Object.entries(st.area_assignee).map(([k, v]: Any) => <div key={k}>{boot.areas[k]} → {name(v)}</div>)}</div>}
        <div className="row"><h2>Time vs budget</h2><span className="sp" />{role !== 'client' && <button className="btn sm" onClick={async () => {
          const v = await ask({ title: 'Log time', fields: [{ key: 'area', label: 'Area', type: 'select', options: Object.keys(st.time.rows.length ? Object.fromEntries(st.time.rows.map((r: Any) => [r.area, 1])) : boot.budget) }, { key: 'hours', label: 'Hours', type: 'number', required: true }, { key: 'note', label: 'Note' }] })
          if (v) send({ type: 'time.logged', payload: { area: v.area, hours: Number(v.hours), note: v.note } }, 'Time logged')
        }}>Log time…</button>}</div>
        <table className="t card"><tbody>{st.time.rows.map((r: Any) => <tr key={r.area}><td>{r.area.replace(/_/g, ' ')}</td><td style={{ width: 160 }}><div className="bar"><i className={r.spent > r.budget ? 'over' : ''} style={{ width: Math.min(100, r.spent / (r.budget || 1) * 100) + '%' }} /></div></td><td className="n num">{r.spent} / {r.budget ? r.budget + ' h' : 'no budget'}</td></tr>)}
          <tr><th>Total</th><th /><th className="n num">{st.time.total_spent} / {st.time.total_budget} h</th></tr></tbody></table>
        <h2>Notifications</h2>{st.inbox.slice(0, 20).map((x: Any, i: number) => <div key={i} className="small" style={{ margin: '4px 0' }}><span className="chip">{x.kind.replace(/_/g, ' ')}</span> {x.text} <span className="muted">{day(x.ts)}</span></div>)}
      </div>
    </div>
  </div>
}

// ---------------------------------------------------------------- Filing
export function Filing() {
  const { st, boot, send, role, ask, go, name } = useApp()
  if (!st || !boot) return null
  const f = st.filing
  const ef = boot.agency.efile
  const sm = st.summary.approved
  const stages = ['in_preparation', 'awaiting_client', 'client_approved', 'submitted', 'rejected', 'filed', 'amending']
  const due = new Date('2026-04-15'), paid = new Date('2026-07-20')
  const months = Math.ceil((+paid - +due) / (30.44 * 864e5))
  const bal = Math.max(0, sm.federal.balance_due)
  const pr = st && boot ? { ftp: Math.round(bal * 0.005 * months), int: Math.round(bal * 0.07 * ((+paid - +due) / (365 * 864e5))) } : { ftp: 0, int: 0 }
  const act = async (type: string, payload: Any = {}, label = 'Recorded') => { try { await send({ type, payload }, label) } catch { } }
  return <div>
    <h1>Filing and after</h1>
    <p className="sub">Extension → client approval (8879) → e-file → rejection handling → acceptance → freeze. Amendments are layered on top of the frozen return; nothing is overwritten.</p>
    {f.frozen_at && <div className="banner frozen">Frozen since {dt(f.frozen_at)} ({f.status}). Return mutations are refused by the server until an amendment is opened.</div>}
    <div className="row" style={{ marginBottom: 12 }}>{stages.map(s => <span key={s} className={'chip ' + (f.status === s ? 'acc' : '')}>{s.replace('_', ' ')}</span>)}</div>
    <div className="grid g2">
      <div className="card"><h2 style={{ marginTop: 0 }}>Actions</h2>
        <div className="small" style={{ marginBottom: 8 }}>Return hash now: <b className="num">{st.return_hash}</b>{f.client_approval && <> · client approved hash <b className="num">{f.client_approval.hash}</b> {f.client_approval.hash === st.return_hash ? <span className="chip ok">matches</span> : <span className="chip err">changed since approval</span>}</>}</div>
        <div className="grid" style={{ gap: 8 }}>
          {!f.extension && <button className="btn" disabled={!['reviewer', 'partner'].includes(role)} onClick={() => act('filing.extension_filed', { federal_form: '4868', federal_paid: boot.what_if.extension.federal.paid_with_form_4868, california_form: 'FTB 3519', california_paid: 0, basis: 'what_if.extension (v2)' }, 'Extension recorded')}>Record extension (4868 with 36,000; FTB 3519 with 0)</button>}
          <button className="btn" disabled={role !== 'partner'} onClick={async () => {
            const blockers = st.steps.filter((x: Any) => !x.done && x.step !== 'Client approval and e-file authorization')
            if (blockers.length) { const v = await ask({ title: 'Not ready to send', text: blockers.map((b: Any) => '• ' + b.step).join('\n'), fields: [{ key: 'override', label: 'Override (partner) — reason', type: 'textarea' }], ok: 'Send anyway' }); if (!v || !v.override) return; act('filing.approval_requested', { override: v.override }, 'Sent to client for approval') }
            else act('filing.approval_requested', {}, 'Sent to client for approval')
          }}>Partner: send to client for approval and 8879</button>
          <button className="btn" disabled={role !== 'partner'} onClick={() => act('filing.efile_submitted', { jurisdictions: ['federal', 'california'] }, 'Transmitted — return frozen')}>Partner: transmit e-file</button>
          <button className="btn" disabled={!['partner', 'firm_administrator'].includes(role)} onClick={() => act('filing.efile_rejected', { ...ef[0], timeline: 'tl-21' }, 'Rejection recorded — return unfrozen for the fix')}>Record federal rejection (R0000-504-02, Theo's SSN)</button>
          <button className="btn" disabled={!['preparer', 'reviewer', 'partner'].includes(role) || (st.facts || []).some((x: Any) => x.path === 'household:theo.ssn')} onClick={async () => { await send([{ type: 'fact.corrected', payload: { path: 'household:theo.ssn', from: '666-74-3309', to: '666-74-3390', evidence: ['D71', 'D06 p1'], note: 'Organizer typo; Social Security card and 2024 return agree' } }, { type: 'finding.accepted', payload: { id: 'DEPENDENT_SSN', reason: 'Corrected to SS card (D71) / 2024 return' } }], 'Theo\'s SSN corrected — amounts unchanged, so the client\'s 8879 still covers this return') }}>Correct Theo's SSN from the SS card (D71)</button>
          <button className="btn" disabled={!['partner', 'firm_administrator'].includes(role)} onClick={() => act('filing.efile_accepted', { federal: ef[2].submission_id, california: ef[3].submission_id, timeline: 'tl-23/tl-24' }, 'Accepted — return frozen')}>Record acceptance (federal 7/14, California 7/15)</button>
          <button className="btn" disabled={role !== 'partner'} onClick={async () => { const v = await ask({ title: 'Open amendment', fields: [{ key: 'reason', label: 'Why (e.g. notice, corrected K-1)', type: 'textarea', required: true }] }); if (v) act('filing.amendment_started', { reason: v.reason }, 'Amendment opened on top of the filed return') }}>Partner: open amendment (1040-X / 540X)</button>
        </div>
        {role === 'client' && <p className="small">Clients approve from their portal.</p>}
        <p className="small muted">Buttons are enabled by role; the server enforces the same rules (try as the wrong person to see the refusal).</p>
      </div>
      <div className="card"><h2 style={{ marginTop: 0 }}>History</h2>
        {f.history.length === 0 && <div className="muted small">No filing events yet.</div>}
        {f.history.map((h: Any, i: number) => <div key={i} className="small" style={{ margin: '5px 0' }}><span className="chip">{h.type.replace('filing.', '')}</span> {name(h.by)} · {dt(h.ts)} {h.errors && <div className="muted">{h.errors.map((e: Any) => e.code + ': ' + e.message).join('; ')}</div>}{h.reason && <div className="muted">{h.reason}</div>}</div>)}
        <h3>Scripted agency events (packet)</h3>{ef.map((e: Any) => <div key={e.submission_id} className="small"><span className={'chip ' + (e.status === 'accepted' ? 'ok' : 'err')}>{e.jurisdiction} {e.status}</span> {dt(e.date)} {e.errors?.map((x: Any) => x.message).join(' ')}</div>)}
        <p className="small">The rejection is predictable: finding <a style={{ cursor: 'pointer' }} onClick={() => go('findings', 'DEPENDENT_SSN')}>DEPENDENT_SSN</a> catches it before transmission by comparing with the 2024 return.</p></div>
    </div>
    <h2>After filing</h2>
    <div className="grid g3">
      <div className="card"><h3 style={{ marginTop: 0 }}>Late payment (federal)</h3><p className="small">Balance on the workpaper return: <b className="num">{money(bal)}</b>. Paid 7/20/2026 vs due 4/15/2026 ({months} months): failure-to-pay ≈ <b className="num">{money(pr.ftp)}</b>, interest ≈ <b className="num">{money(pr.int)}</b> (0.5%/month, 7%/yr). {bal === 0 && 'The corrected return shows an overpayment, so the scripted 7/20 "balance paid" event and the 196/276 assessment would not occur — flagged for the partner.'}</p></div>
      <div className="card"><h3 style={{ marginTop: 0 }}>Records</h3><div className="grid" style={{ gap: 6 }}>
        <a className="btn" href="/api/export/notice/N-2025-L566" target="_blank" onClick={e => { e.preventDefault(); openAs('/api/export/notice/N-2025-L566') }}>Answer Letter 566 (2028) — self-contained record</a>
        <button className="btn" onClick={() => openAsk({ mode: 'draft_notice_response' })}>✦ Draft the Letter 566 narrative (AI, cited)</button>
        <a className="btn" href="#" onClick={e => { e.preventDefault(); openAs('/api/export/client-copy') }}>Client copy</a>
        <a className="btn" href="#" onClick={e => { e.preventDefault(); openAs('/api/export/workpaper') }}>Full workpaper record</a>
        <a className="btn" href="#" onClick={e => { e.preventDefault(); openAs('/api/export/rollforward', true) }}>Roll forward to 2026 (JSON)</a></div></div>
      <div className="card"><h3 style={{ marginTop: 0 }}>Plan next year</h3><p className="small">{boot.agency && 'Safe harbor: 110% of 2025 tax.'} Federal ≈ <b className="num">{money(Math.round(sm.federal.total_tax * 1.1))}</b> ({money(Math.round(sm.federal.total_tax * 1.1 / 4))} per quarter, due 4/15, 6/15, 9/15, 1/15). California only taxes CA-source income in 2026 (Fremont rental, Ridgeline share); 110% of 2025 CA tax ≈ <b className="num">{money(Math.round(sm.california.total_tax * 1.1))}</b> — likely far above need; annualize. Minimum tax credit from the 2025 AMT may be usable (Form 8801).</p></div>
    </div>
  </div>
}

async function openAs(path: string, json = false) {
  const r = await fetch(path, { headers: { 'X-Person': localStorage.getItem('wp.person') || 'st-01' } })
  const t = await r.text()
  const blob = new Blob([json ? JSON.stringify(JSON.parse(t), null, 2) : t], { type: json ? 'application/json' : 'text/html' })
  window.open(URL.createObjectURL(blob), '_blank')
}

// ---------------------------------------------------------------- Timeline
const humanize = (t: string) => ({ 'adjustment.proposed': 'proposed an adjustment', 'adjustment.approved': 'approved an adjustment', 'adjustment.reversed': 'reversed an adjustment',
  'verification.added': 'verified', 'verification.removed': 'withdrew a verification', 'note.created': 'added a note', 'note.replied': 'replied to a note', 'note.resolved': 'resolved a note',
  'note.reopened': 'reopened a note', 'question.asked': 'asked a question', 'question.answered': 'answered a question', 'signoff.signed': 'signed off', 'finding.accepted': 'accepted a finding',
  'finding.dismissed': 'dismissed a finding', 'finding.reopened': 'reopened a finding', 'time.logged': 'logged time', 'file.attached': 'attached a file', 'link.added': 'linked items',
  'view.sensitive': 'viewed sensitive data', 'batch.undo': 'undid a batch', 'batch.redo': 'redid a batch', 'fact.corrected': 'corrected a fact', 'standards.updated': 'changed firm standards',
  'assignment.set': 'assigned work', 'ai.answered': 'asked the assistant' } as Record<string, string>)[t] || t.replace('filing.', 'filing: ').replace(/_/g, ' ')

export function Timeline() {
  const { st, boot, name, arg, person, send, go } = useApp()
  const [evs] = useLoad<Any[]>('/api/events?since=0')
  const [asof, setAsof] = useState('2028-12-31')
  if (!st || !boot || !evs) return <div className="empty">Loading…</div>
  const since = arg === 'since' ? st.changes.since_event : null
  const items = [
    ...boot.timeline.map((t: Any) => ({ at: t.at, who: t.actor ? name(t.actor) : 'client / system', what: t.event.replace(/_/g, ' '), detail: t.detail || t.refs.join(', '), src: 'packet' })),
    ...evs.filter(e => e.type !== 'view.seen').map(e => ({ at: e.ts, who: name(e.actor), actorId: e.actor, what: humanize(e.type), detail: e.payload.description || e.payload.text || e.payload.reason || e.payload.vtype || e.payload.what || e.entity || '', src: 'workpaper', id: e.id, batch: e.batch, undone: st.undone_batches.includes(e.batch) })),
  ].filter(x => x.at <= asof + 'T99' && (since === null || (x.src === 'workpaper' && x.id > since && x.actorId !== person))).sort((a, b) => a.at < b.at ? 1 : -1)
  return <div>
    <h1>{since !== null ? 'What changed since you last looked' : 'Season timeline'}</h1>
    <p className="sub">The packet's scripted season merged with every workpaper event. Filter to any date to see the season as it stood then.</p>
    {since !== null && <div className="row" style={{ marginBottom: 8 }}><button className="btn pri" onClick={async () => { await send({ type: 'view.seen', payload: { event_id: st.last_event } }); go('overview') }}>Mark all as seen</button><span className="small muted">Only you clear this list.</span></div>}
    <div className="row"><span className="small">As of</span><input type="date" value={asof} onChange={e => setAsof(e.target.value)} className="btn" />
      {['2026-03-04', '2026-03-19', '2026-04-14', '2026-06-23', '2026-07-15', '2028-12-31'].map(d => <button key={d} className="btn sm" onClick={() => setAsof(d)}>{d}</button>)}</div>
    <table className="t card" style={{ marginTop: 10 }}><thead><tr><th>When</th><th>Source</th><th>Who</th><th>Event</th><th>Detail</th></tr></thead><tbody>
      {items.slice(0, 400).map((x, i) => <tr key={i} style={{ opacity: x.undone ? .45 : 1 }}><td className="small num">{dt(x.at)}</td><td><span className={'chip ' + (x.src === 'packet' ? '' : 'acc')}>{x.src}</span></td><td className="small">{x.who}</td><td>{x.what}{x.undone && <span className="chip">undone</span>}</td><td className="small">{String(x.detail).slice(0, 140)}</td></tr>)}</tbody></table>
  </div>
}

// ---------------------------------------------------------------- Compare & what-if
export function Compare() {
  const { boot, st, trace } = useApp()
  const [a, setA] = useState('v2')
  const [b, setB] = useState('v3')
  const [d] = useLoad<Any>(`/api/compare?a=${a}&b=${b}`, [a, b])
  const [rows, setRows] = useState<Any[]>([{ line: 'Sch1.16', delta: 2786, category: 'adjustment' }])
  const [res, setRes] = useState<Any>(null)
  if (!boot) return null
  const opts = [...boot.packet.versions.map((v: Any) => v.version), 'workpaper']
  return <div>
    <h1>Compare versions and try what-ifs</h1>
    <div className="row"><select className="btn" value={a} onChange={e => setA(e.target.value)}>{opts.map((o: string) => <option key={o}>{o}</option>)}</select>→<select className="btn" value={b} onChange={e => setB(e.target.value)}>{opts.map((o: string) => <option key={o}>{o}</option>)}</select>
      {d && b in d.meta && <span className="small muted">{b}: {d.meta[b].trigger}</span>}</div>
    {d && <><div className="grid g2" style={{ marginTop: 10 }}>{(['federal', 'california'] as const).map(j => <div key={j} className="card small"><b>{j}</b> total tax {money(d.summary_a[j].total_tax)} → {money(d.summary_b[j].total_tax)} · balance {money(d.summary_a[j].balance_due)} → {money(d.summary_b[j].balance_due)}</div>)}</div>
      <table className="t card" style={{ marginTop: 10 }}><thead><tr><th>Line</th><th>Label</th><th className="n">{a}</th><th className="n">{b}</th><th className="n">Δ</th></tr></thead><tbody>
        {d.rows.slice(0, 300).map((r: Any) => <tr key={r.key} className="click" onClick={() => trace({ kind: 'line', id: r.key })}><td className="num small">{r.key}</td><td className="small">{r.label}</td><td className="n num">{fmtVal(r.a)}</td><td className="n num">{fmtVal(r.b)}</td><td className="n num">{r.delta !== null ? signed(r.delta) : ''}</td></tr>)}</tbody></table>
      <p className="small muted">{d.rows.length} lines differ.</p></>}
    <h2>Engine what-ifs (computed by the engine)</h2>
    <table className="t card"><thead><tr><th>Alternative</th><th className="n">Federal tax Δ</th><th className="n">California tax Δ</th><th className="n">Lines changed</th></tr></thead><tbody>
      {boot.what_if.alternatives.map((w: Any) => <tr key={w.id}><td>{w.description}</td><td className="n num">{signed(w.federal.total_tax_change)}</td><td className="n num">{signed(w.california.total_tax_change)}</td><td className="n num">{w.changed_lines.length}{w.changed_lines.length === 0 && <span className="chip warn" style={{ marginLeft: 4 }}>no effect</span>}</td></tr>)}</tbody></table>
    <h2>Sandbox what-if (nothing is saved)</h2>
    <div className="card">{rows.map((r, i) => <div key={i} className="row" style={{ marginBottom: 6 }}><input className="btn" value={r.line} onChange={e => { const n = [...rows]; n[i] = { ...r, line: e.target.value }; setRows(n) }} placeholder="line" />
      <input className="btn" type="number" value={r.delta} onChange={e => { const n = [...rows]; n[i] = { ...r, delta: Number(e.target.value) }; setRows(n) }} />
      <select className="btn" value={r.category} onChange={e => { const n = [...rows]; n[i] = { ...r, category: e.target.value }; setRows(n) }}>{CATEGORIES.map(c => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}</select>
      <button className="btn sm" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button></div>)}
      <div className="row"><button className="btn sm" onClick={() => setRows([...rows, { line: '', delta: 0, category: 'ordinary_income' }])}>+ change</button><button className="btn sm pri" onClick={async () => setRes(await post('/api/whatif', { changes: rows }))}>Run</button></div>
      {res && <p className="small">Federal tax <b className="num">{signed(res.federal_tax_change)}</b> → balance {money(res.federal_balance_due)} · California <b className="num">{signed(res.california_tax_change)}</b> → balance {money(res.california_balance_due)}<br /><span className="muted">{res.caveat}</span></p>}</div>
  </div>
}

// ---------------------------------------------------------------- Firm
export function Firm() {
  const { st, boot, send, role, ask, name, refresh, toast } = useApp()
  if (!st || !boot) return null
  const s = st.standards
  const edit = async () => {
    const v = await ask({ title: 'Firm standards', text: 'Changes apply firm-wide and are recorded as events.', fields: [
      { key: 'pct', label: 'Variance flag: over %', type: 'number', value: s.variance_review.flag_if_change_over_percent },
      { key: 'amt', label: 'Variance flag: and over amount', type: 'number', value: s.variance_review.and_over_amount },
      { key: 'thr', label: 'Partner sign-off threshold (tax effect)', type: 'number', value: 1000 },
      { key: 'vt', label: 'Verification types (comma-separated)', value: s.verification_types.join(', ') }] })
    if (!v) return
    const rules = s.rules.map((r: string) => r.includes('requires partner sign-off') ? `Any adjustment with a tax effect over ${Number(v.thr).toLocaleString()} (federal or state) requires partner sign-off.` : r)
    send({ type: 'standards.updated', payload: { standards: { variance_review: { ...s.variance_review, flag_if_change_over_percent: Number(v.pct), and_over_amount: Number(v.amt) }, verification_types: v.vt.split(',').map((x: string) => x.trim()).filter(Boolean), rules } } }, 'Firm standards updated')
  }
  const [busy, setBusy] = useState<string | null>(null)
  const [armReset, setArmReset] = useState(false)
  const admin = async (path: string, label: string, key: string) => { setBusy(key); try { await post(path, {}); await refresh(); toast(label) } catch (e: Any) { toast('⚠ ' + e.message) } setBusy(null); setArmReset(false) }
  return <div>
    <h1>Firm</h1>
    <div className="grid g2">
      <div className="card"><div className="row"><h2 style={{ marginTop: 0 }}>Standards</h2><span className="sp" />{can(role, 'standards') ? <button className="btn sm pri" onClick={edit}>Edit</button> : <span className="small muted">firm administrator edits</span>}</div>
        <div className="small"><b>Verification types:</b> {s.verification_types.join(', ')}</div>
        <div className="small"><b>Variance review:</b> over {s.variance_review.flag_if_change_over_percent}% and over {money(s.variance_review.and_over_amount)} vs prior year</div>
        <div className="small"><b>Review levels:</b> {s.review_levels.join(' → ')}</div>
        <h3>Rules (enforced server-side)</h3><ul className="small">{s.rules.map((r: string) => <li key={r}>{r}</li>)}</ul>
        <h3>Required steps (filing gates)</h3><ol className="small">{s.required_steps.map((r: string) => <li key={r}>{r}</li>)}</ol></div>
      <div>
        <div className="card"><h2 style={{ marginTop: 0 }}>Sensitive data</h2>
          <p className="small">SSNs, bank and account numbers, IP PINs and signature PINs are masked in every API response. Cleared staff can reveal one value at a time; every reveal — and every refused attempt — is logged.</p>
          <RevealDemo />
          <h3>View log</h3>{['firm_administrator', 'partner'].includes(role) ? (st.view_log.length ? <table className="t small"><tbody>{st.view_log.map((v: Any, i: number) => <tr key={i}><td className="num">{dt(v.ts)}</td><td>{name(v.by)}</td><td>{v.what}</td><td>{v.granted ? <span className="chip ok">revealed</span> : <span className="chip err">refused</span>}</td><td className="muted">{v.context}</td></tr>)}</tbody></table> : <div className="muted small">No views yet.</div>) : <div className="muted small">Visible to the administrator and partner.</div>}
          <p className="small muted">Retention: records kept 7 years after filing (to 2033), then destroyed — per firm rule.</p></div>
        <div className="card" style={{ marginTop: 14 }}><h2 style={{ marginTop: 0 }}>Demo data</h2>
          <p className="small">The packet itself is never modified. "Load demo season" replays a plausible March–June of team work (accepted findings, approvals, a reopened sign-off, blocking review notes). "Reset" returns to the bare packet.</p>
          <div className="row"><button className="btn pri" disabled={!can(role, 'admin') || !!busy} onClick={() => admin('/api/admin/seed', 'Demo season loaded — open Overview to see it', 'seed')}>{busy === 'seed' ? 'Loading demo season…' : 'Load demo season'}</button>
            {!armReset ? <button className="btn danger" disabled={!can(role, 'admin') || !!busy} onClick={() => setArmReset(true)}>Reset…</button> :
              <><button className="btn danger" disabled={!!busy} onClick={() => admin('/api/admin/reset', 'Reset to bare packet', 'reset')}>{busy === 'reset' ? 'Resetting…' : 'Yes, erase all workpaper events'}</button><button className="btn" onClick={() => setArmReset(false)}>Cancel</button></>}</div>
          <p className="small muted">Packet: {boot.packet.name} v{boot.packet.version} · sha256 {boot.packet.sha256}</p></div>
      </div>
    </div>
  </div>
}

function RevealDemo() {
  const { boot, toast, refresh } = useApp()
  const [v, setV] = useState<Any>({})
  const fields = [...boot.household.people.map((p: Any) => ['ssn:' + p.id, 'SSN ' + p.name.split(' ')[0]]), ['ip_pin:ngozi', 'IP PIN Ngozi'], ['bank:account', 'Refund account'], ['foreign:account', 'Sparbanken IBAN']]
  return <div className="row" style={{ gap: 6 }}>{fields.map(([k, l]: Any) => <button key={k} className="chip" onClick={async () => {
    try { const r = await post('/api/unmask', { what: k, context: 'Firm page' }); setV({ ...v, [k]: r.value }); refresh() } catch (e: Any) { toast('⚠ ' + e.message); refresh() }
  }}>{l}: {v[k] || '•••• reveal'}</button>)}</div>
}

// ---------------------------------------------------------------- Client portal
export function ClientPortal() {
  const { st, boot, send, name, person, refresh, toast } = useApp()
  const [docs] = useLoad<Any[]>('/api/documents')
  if (!st || !boot) return null
  const sm = st.summary.approved
  const f = st.filing
  const upload = () => {
    const inp = document.createElement('input'); inp.type = 'file'
    inp.onchange = async () => { const fl = inp.files?.[0]; if (!fl) return; const fd = new FormData(); fd.append('file', fl); fd.append('target', 'client-upload'); await api('/api/files', { method: 'POST', body: fd }); await refresh(); toast('Uploaded — your CPA team has been notified') }
    inp.click()
  }
  return <div style={{ maxWidth: 880 }}>
    <div className="client-hero"><div className="small" style={{ opacity: .8 }}>Welcome, {name(person)}</div><h1 style={{ color: '#fff' }}>Your 2025 tax return</h1>
      <div className="grid g2" style={{ marginTop: 10 }}><div><div className="small" style={{ opacity: .8 }}>Federal (estimated)</div><div className="num">{sm.federal.balance_due > 0 ? `About ${money(sm.federal.balance_due)} due` : `About ${money(-sm.federal.balance_due)} refund`}</div></div>
        <div><div className="small" style={{ opacity: .8 }}>California (estimated)</div><div className="num">{sm.california.balance_due > 0 ? `About ${money(sm.california.balance_due)} due` : `About ${money(-sm.california.balance_due)} refund`}</div></div></div>
      <div className="small" style={{ opacity: .8, marginTop: 6 }}>Estimates while your CPA team finishes review; final amounts come with the return you approve.</div>
      <div className="small" style={{ opacity: .8, marginTop: 8 }}>Status: {f.status.replace('_', ' ')}{f.extension && ' · extension filed 4/14'}</div></div>
    {f.status === 'awaiting_client' && <div className="card" style={{ marginTop: 14, borderColor: 'var(--accent)' }}><h2 style={{ marginTop: 0 }}>Ready for your approval</h2><p>Please review the summary. Approving signs Forms 8879 and FTB 8879 electronically for both of you.</p>
      <div className="row"><a className="btn" href="#" onClick={e => { e.preventDefault(); openAs('/api/export/client-copy') }}>Review return summary</a><button className="btn pri" onClick={() => send({ type: 'filing.client_approved', payload: { signed: '8879 and FTB 8879', signer: person } }, 'Thank you — approval and e-file signature recorded')}>Approve and sign</button></div></div>}
    <h2>Questions from your CPA team</h2>
    {st.questions.length === 0 && <div className="empty">No questions right now.</div>}{st.questions.map((q: Any) => <QuestionCard key={q.id} q={q} />)}
    <div className="row"><h2>Your documents</h2><span className="sp" /><button className="btn pri" onClick={upload}>Upload a document</button></div>
    <table className="t card"><tbody>{(docs || []).map((d: Any) => <tr key={d.id}><td>{d.title}</td><td className="small muted">{d.received_at.slice(0, 10)}</td><td>{d.status === 'landed' || d.status === 'explained' ? <span className="chip ok">received & used</span> : <span className="chip">received</span>}</td></tr>)}
      {st.files.filter((x: Any) => x.target === 'client-upload').map((x: Any) => <tr key={x.id}><td>📎 {x.name}</td><td className="small muted">{x.ts.slice(0, 10)}</td><td><span className="chip warn">new</span></td></tr>)}</tbody></table>
    <p className="small muted">You see your own documents, questions and approvals. Your SSNs and account numbers are masked on screen.</p>
  </div>
}
