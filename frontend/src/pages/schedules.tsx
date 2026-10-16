import React, { useMemo, useState } from 'react'
import { Any, Num, Ref, can, dt, fmtVal, money, signed, useApp, useLoad } from '../lib'
import { useActions } from '../trace'

const TABS = [['summary', 'Return vs last year'], ['taxcomp', 'Tax computation'], ['sales', 'Sales detail'], ['assets', 'Depreciation'], ['books', 'Books to tax'],
  ['rentals', 'Rentals & passive'], ['k1', 'K-1s'], ['basis', 'Basis by year'], ['carry', 'Carryovers'], ['ded', 'Deductions & credits'], ['retire', 'Retirement & foreign'],
  ['state', 'State split'], ['payments', 'Payments'], ['prior', 'Prior preparer vs us']]

export function Schedules() {
  const { arg, go } = useApp()
  const tab = arg || 'summary'
  return <div>
    <h1>Schedules</h1>
    <p className="sub">The records a CPA expects, each number clickable to its trace.</p>
    <div className="tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => go('schedules', k)}>{l}</button>)}</div>
    {tab === 'summary' && <SummaryVsPY />}{tab === 'taxcomp' && <LineList keys={TAXCOMP} />}{tab === 'sales' && <Sales />}{tab === 'assets' && <Assets />}
    {tab === 'books' && <Books />}{tab === 'rentals' && <LineList keys={RENTALS} />}{tab === 'k1' && <K1 />}{tab === 'basis' && <Basis />}{tab === 'carry' && <Carry />}
    {tab === 'ded' && <LineList keys={DED} />}{tab === 'retire' && <LineList keys={RETIRE} />}{tab === 'state' && <StateSplit />}{tab === 'payments' && <Payments />}{tab === 'prior' && <Prior />}
  </div>
}

const TAXCOMP = ['F1040.1z', 'F1040.2b', 'F1040.3b', 'F1040.4b', 'F1040.7', 'F1040.8', 'F1040.9', 'F1040.10', 'F1040.11', 'F1040.12', 'F1040.13', 'F1040.15', 'F1040.16', 'F1040.17', 'F1040.19', 'F1040.20', 'F1040.22', 'Sch2.4', 'Sch2.11', 'Sch2.12', 'F1040.23', 'F1040.24', 'F1040.25d', 'F1040.26', 'F1040.31', 'F1040.33', 'F1040.37', 'F1040.38']
const RENTALS = ['SchE.3A', 'SchE.9A', 'SchE.11A', 'SchE.12A', 'SchE.14A', 'SchE.16A', 'SchE.18A', 'SchE.21A', 'SchE.3B', 'SchE.9B', 'SchE.12B', 'SchE.14B', 'SchE.16B', 'SchE.18B', 'SchE.19B', 'SchE.21B', 'F4797.21', 'F4797.22', 'F4797.23', 'F4797.25', 'SchD.19', 'F8582.1a', 'F8582.1b', 'F8582.1c', 'F8582.3a', 'F8582.4', 'SchE.22A', 'SchE.22B', 'SchE.26']
const DED = ['SchA.5a', 'SchA.5b', 'SchA.5d', 'SchA.5e', 'SchA.8a', 'SchA.8c', 'SchA.10', 'SchA.11', 'F8283.A1.stock', 'F8283.A1.vehicle', 'SchA.14', 'SchA.17', 'F8812.5', 'F8812.7', 'F8812.11', 'F8812.12', 'F8863.30', 'F8863.7', 'F2441.2', 'F2441.12', 'F2441.31', 'F8995.15.1', 'F8995.15.2', 'F8995.36', 'F8995.39', 'Sch3.1', 'F8867.status']
const RETIRE = ['F8606.1', 'F8606.2', 'F8606.6', 'F8606.8', 'F8606.18', 'F1040.4a', 'F1040.4b', 'Sch1.16', 'F8889.3', 'F8889.9', 'F8889.14a', 'F8889.16', 'SchB.1.6', 'SchB.7a', 'SchB.7b', 'SchB.8', 'F8938.1.max', 'F8938.1.ye', 'F8938.req', 'Sch3.1']

function LineList({ keys }: { keys: string[] }) {
  const [lines] = useLoad<Any[]>('/api/lines')
  if (!lines) return <div className="empty">Loading…</div>
  const m = Object.fromEntries(lines.map(l => [l.key, l]))
  return <table className="t card"><thead><tr><th>Line</th><th>Label</th><th className="n">Engine</th><th className="n">Workpaper</th><th>Rule</th><th></th></tr></thead><tbody>
    {keys.filter(k => m[k]).map(k => { const l = m[k]; return <tr key={k}><td className="num small">{k}</td><td>{l.label}{l.note && <div className="small muted">{l.note}</div>}</td><td className="n"><Num k={k} v={l.value} /></td>
      <td className="n">{l.pending !== l.value || l.stale ? <Num k={k} v={l.value} adj={l.pending} stale={l.stale} /> : <span className="muted">=</span>}</td><td className="small muted">{l.rule}</td><td>{l.verified.length > 0 && <span className="chip ok">✓</span>}{l.adjustments > 0 && <span className="chip warn">±</span>}</td></tr> })}
  </tbody></table>
}

function SummaryVsPY() {
  const [d] = useLoad<Any>('/api/schedules/prior-year')
  const a = useActions()
  const { role, send, ask } = useApp()
  const [all, setAll] = useState(false)
  if (!d) return <div className="empty">Loading…</div>
  const rows = d.variances.filter((v: Any) => all || v.flagged)
  const unexplained = d.variances.filter((v: Any) => v.flagged && !v.explained)
  const bulk = async () => {
    const v = await ask({ title: `Explain ${unexplained.length} variances`, text: 'Applies one explanation to every flagged, unexplained line (one batch, one undo). Use for structural causes, then refine individually.', fields: [{ key: 'text', label: 'Explanation', type: 'textarea', value: '2025 differs structurally from 2024: part-year CA → TX move, condo sale, new employer and stock compensation, late K-1, and the workpaper corrections listed in Findings.', required: true }] })
    if (v) send(unexplained.map((x: Any) => ({ type: 'note.created', payload: { target: 'line:' + x.key, kind: 'variance_explanation', text: v.text } })), `${unexplained.length} variances explained`)
  }
  return <div>
    <div className="row"><span className="small">Flag rule (firm standard): change over 10% <i>and</i> over 1,000 vs 2024 filed. {unexplained.length} flagged lines unexplained.</span><span className="sp" />
      <label className="small"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} /> show all lines</label>
      {can(role, 'judgment') && unexplained.length > 0 && <button className="btn sm" onClick={bulk}>Explain in bulk…</button>}</div>
    <table className="t card" style={{ marginTop: 8 }}><thead><tr><th>Line</th><th>Label</th><th className="n">2024 filed</th><th className="n">2025 workpaper</th><th className="n">Change</th><th className="n">%</th><th>Explanation</th></tr></thead><tbody>
      {rows.map((v: Any) => <tr key={v.key}><td className="num small">{v.key}</td><td>{v.label}</td><td className="n num">{money(v.prior)}</td><td className="n">{v.in_2025 ? <Num k={v.key} v={v.current} /> : <span className="muted">not on 2025</span>}</td>
        <td className={'n num ' + (v.change > 0 ? 'diffneg' : 'diffpos')}>{signed(v.change)}</td><td className="n num">{v.pct}%</td>
        <td className="small">{v.flagged ? (v.explained ? <span><span className="chip ok">✓</span> {v.explanation?.slice(0, 90)}</span> : <button className="btn sm" onClick={() => a.note('line:' + v.key, ['variance_explanation'])}>Explain</button>) : <span className="muted">under threshold</span>}</td></tr>)}
    </tbody></table>
  </div>
}

function Sales() {
  const [d] = useLoad<Any>('/api/schedules/sales')
  const [broker, setBroker] = useState('all')
  const [term, setTerm] = useState('all')
  const [q, setQ] = useState('')
  const [pageN, setPageN] = useState(0)
  const { trace } = useApp()
  const rows = useMemo(() => (d?.rows || []).filter((r: Any) => (broker === 'all' || r.broker === broker) && (term === 'all' || r.term === term) && (!q || r.name.toLowerCase().includes(q.toLowerCase()) || r.lot.toLowerCase() === q.toLowerCase())), [d, broker, term, q])
  if (!d) return <div className="empty">Loading…</div>
  const per = 50
  return <div>
    <h2>Reconciliation to broker statements</h2>
    <table className="t card"><thead><tr><th>Statement</th><th className="n">Statement proceeds</th><th className="n">Sum of lots</th><th>Agrees?</th><th>Note</th></tr></thead><tbody>
      {d.reconciliation.map((r: Any, i: number) => <tr key={i}><td>{r.statement} <Ref r={{ type: 'doc', id: r.doc }} /></td><td className="n num">{money(r.statement_proceeds, 2)}</td><td className="n num">{money(r.lots_proceeds, 2)}</td><td>{r.ok ? <span className="chip ok">✓</span> : <span className="chip err">✗ {money(r.statement_proceeds - r.lots_proceeds, 2)}</span>}</td><td className="small">{r.note} {(r.note_refs || []).map((x: Any, j: number) => <Ref key={j} r={x} />)}</td></tr>)}</tbody></table>
    <h2>By broker and term</h2>
    <table className="t card"><thead><tr><th>Broker</th><th>Term</th><th className="n">Lots</th><th className="n">Proceeds</th><th className="n">Basis</th><th className="n">Adjustments</th><th className="n">Gain/(loss)</th></tr></thead><tbody>
      {d.groups.map((g: Any, i: number) => <tr key={i} className="click" onClick={() => { setBroker(g.broker); setTerm(g.term); setPageN(0) }}><td>{g.broker}</td><td>{g.term}</td><td className="n num">{g.count}</td><td className="n num">{money(g.proceeds)}</td><td className="n num">{money(g.basis)}</td><td className="n num">{money(g.adj)}</td><td className="n num">{money(g.gain)}</td></tr>)}</tbody></table>
    <h2>Lots ({rows.length})</h2>
    <div className="row" style={{ marginBottom: 8 }}><select className="btn" value={broker} onChange={e => { setBroker(e.target.value); setPageN(0) }}>{['all', 'Northlake', 'Meridian', 'Brightpath', 'Coinhaven', 'Woodworks (S corp)'].map(x => <option key={x}>{x}</option>)}</select>
      <select className="btn" value={term} onChange={e => { setTerm(e.target.value); setPageN(0) }}>{['all', 'short', 'long'].map(x => <option key={x}>{x}</option>)}</select>
      <input placeholder="security or lot id" value={q} onChange={e => { setQ(e.target.value); setPageN(0) }} style={{ padding: '6px 10px', border: '1px solid var(--line)', borderRadius: 8 }} />
      <span className="sp" /><button className="btn sm" disabled={pageN === 0} onClick={() => setPageN(pageN - 1)}>‹</button><span className="small">{pageN * per + 1}–{Math.min(rows.length, (pageN + 1) * per)}</span><button className="btn sm" disabled={(pageN + 1) * per >= rows.length} onClick={() => setPageN(pageN + 1)}>›</button></div>
    <table className="t card"><thead><tr><th>Lot</th><th>Box</th><th>Security</th><th>Acquired</th><th>Sold</th><th className="n">Proceeds</th><th className="n">Basis</th><th className="n">Adj.</th><th className="n">Gain</th><th>Source</th></tr></thead><tbody>
      {rows.slice(pageN * per, (pageN + 1) * per).map((r: Any) => <tr key={r.key}><td className="num small">{r.lot}</td><td>{r.box}</td><td>{r.name}{r.flag && <span className="chip err" style={{ marginLeft: 4 }}>{r.flag}</span>}</td><td className="small num">{r.acquired}</td><td className="small num">{r.sold}</td>
        <td className="n num">{money(r.proceeds, 2)}</td><td className="n num">{money(r.basis, 2)}</td><td className="n num">{r.adj ? `${r.adj_code} ${money(r.adj, 2)}` : ''}</td><td className="n"><Num k={r.key} v={r.gain} adj={r.adjusted_gain} /></td>
        <td>{r.doc && <button className="chip" onClick={() => trace({ kind: 'doc', id: r.doc, page: r.page })}>{r.doc} p{r.page}</button>}{r.verified && <span className="chip ok">✓</span>}</td></tr>)}</tbody></table>
  </div>
}

function Assets() {
  const [d] = useLoad<Any>('/api/schedules/assets')
  if (!d) return <div className="empty">Loading…</div>
  const all = [...d.assets, ...d.proposed]
  return <div>
    <table className="t card"><thead><tr><th>Asset</th><th>Placed in service</th><th>Method / life</th><th className="n">Cost</th><th className="n">Federal 2025</th><th className="n">Fed accumulated</th><th className="n">California 2025</th><th className="n">CA accumulated</th><th className="n">AMT diff.</th><th>Disposal</th></tr></thead><tbody>
      {all.map((a: Any) => <tr key={a.asset_id}><td><b>{a.asset_id}</b><div className="small muted">{a.description}</div>{a.status && <span className="chip warn">{a.status}</span>}</td><td className="small num">{a.placed_in_service}</td><td className="small">{a.method} · {a.life_years} yr{a.land_value_not_depreciated ? <div className="muted">land {money(a.land_value_not_depreciated)} not depreciated</div> : null}</td>
        <td className="n num">{money(a.cost)}</td><td className="n num">{money(a.federal?.depreciation_2025, 2)}</td><td className="n num">{money(a.federal?.accumulated_end, 2)}</td><td className="n num">{money(a.california?.depreciation_2025, 2)}</td><td className="n num">{money(a.california?.accumulated_end, 2)}</td>
        <td className="n num">{money(a.amt?.difference_from_regular, 2)}</td><td className="small">{a.disposition ? <>sold {a.disposition.date}; unrecaptured §1250 {money(a.disposition.unrecaptured_1250_depreciation, 2)}; §1250 ordinary {money(a.disposition.section_1250_ordinary_recapture)}</> : ''}</td></tr>)}</tbody></table>
    <h3>California basis differences carried forward</h3>
    <div className="row">{Object.entries(d.ca_differences).map(([k, v]: Any) => <span key={k} className="chip">{k}: {money(v, 2)}</span>)}</div>
    <p className="small muted">Bonus vs §179 vs MACRS for the 38,000 of studio equipment: see Compare → engine what-ifs (federal +0 / +10,245; California −1,050 / −260).</p>
  </div>
}

function Books() {
  const [d] = useLoad<Any>('/api/schedules/books-to-tax')
  if (!d) return <div className="empty">Loading…</div>
  const r = d.receipts
  return <div className="grid g2">
    <div className="card"><h2 style={{ marginTop: 0 }}>Book income → Schedule C</h2>
      <table className="t"><tbody>{d.items.map((x: Any, i: number) => <tr key={i}><td>{x.label}<div className="small muted">{x.ref}</div></td><td className="n num">{money(x.amount)}</td></tr>)}
        <tr><th>Schedule C net profit (engine)</th><th className="n"><Num k="SchC.31" v={d.engine_schc_31} /></th></tr>
        {d.workpaper.map((x: Any) => <tr key={x.id}><td>{x.label} <span className={'chip ' + (x.status === 'approved' ? 'ok' : 'warn')}>{x.status}</span></td><td className="n num">{money(x.amount)}</td></tr>)}
        <tr><th>Schedule C net profit (workpaper, approved)</th><th className="n num">{money(d.workpaper_schc_31)}</th></tr></tbody></table>
      <div className="small">{d.foots ? <span className="chip ok">✓ reconciliation foots to engine</span> : <span className="chip err">does not foot</span>}</div></div>
    <div className="card"><h2 style={{ marginTop: 0 }}>Gross receipts vs information returns</h2>
      <table className="t"><tbody>
        <tr><td>Forms 1099-NEC (5 payers) <Ref r={{ type: 'doc', id: 'D16' }} /><Ref r={{ type: 'doc', id: 'D17' }} /><Ref r={{ type: 'doc', id: 'D18' }} /><Ref r={{ type: 'doc', id: 'D19' }} /><Ref r={{ type: 'doc', id: 'D20' }} /></td><td className="n num">{money(r.forms_1099_nec)}</td></tr>
        <tr><td>Form 1099-K (Paywell) <Ref r={{ type: 'doc', id: 'D21' }} /></td><td className="n num">{money(r.form_1099_k)}</td></tr>
        <tr><td>Less: Atlas card payments reported on both <Ref r={{ type: 'doc', id: 'D15', page: 3 }} /></td><td className="n num">({money(r.atlas_paid_by_card_in_1099k)})</td></tr>
        <tr><td>Clients with no 1099 (11) <Ref r={{ type: 'doc', id: 'D15', page: 3 }} /></td><td className="n num">{money(r.no_1099_clients)}</td></tr>
        <tr><th>Explained receipts</th><th className="n num">{money(r.explained)}</th></tr>
        <tr><th>Books revenue <Ref r={{ type: 'doc', id: 'D14' }} /></th><th className="n num">{money(r.books_revenue)}</th></tr></tbody></table>
      <p className="small">{r.explained === r.books_revenue ? <span className="chip ok">✓ every receipt dollar explained</span> : <span className="chip err">unexplained {money(r.books_revenue - r.explained)}</span>} This table is item 2 of the 2028 Letter 566.</p></div>
  </div>
}

function K1() {
  const [d] = useLoad<Any>('/api/schedules/k1')
  if (!d) return <div className="empty">Loading…</div>
  return <div><table className="t card"><thead><tr><th>K-1</th><th>Box</th><th>Label</th><th className="n">K-1 amount</th><th>Return line</th><th className="n">Line value</th></tr></thead><tbody>
    {d.rows.map((r: Any, i: number) => <tr key={i}><td><Ref r={{ type: 'ev', id: r.ev, doc: r.doc }}>{r.doc}</Ref></td><td className="num">{r.box}</td><td>{r.label}</td><td className="n num">{fmtVal(r.value)}</td><td>{r.line ? <Ref r={{ type: 'line', id: r.line }} /> : <span className="muted small">memo (basis)</span>}</td><td className="n num">{fmtVal(r.line_value)}</td></tr>)}</tbody></table>
    {d.late.map((l: Any, i: number) => <p key={i} className="small"><span className="chip warn">late</span> {l.doc} received {dt(l.received)} — {l.note}</p>)}</div>
}

function Basis() {
  const [d] = useLoad<Any>('/api/schedules/basis')
  if (!d) return <div className="empty">Loading…</div>
  return <div>
    <h2>Lindqvist Family Woodworks — S corporation stock basis (Form 7203)</h2>
    <table className="t card"><thead><tr><th>Year</th><th className="n">Beginning</th><th className="n">Income</th><th className="n">Distributions</th><th className="n">Ending</th><th className="n">Excess → gain</th><th>Source</th></tr></thead><tbody>
      {d.scorp.map((r: Any) => <tr key={r.year}><td>{r.year}</td><td className="n num">{money(r.begin)}</td><td className="n num">{money(r.income)}</td><td className="n num">{money(r.distributions)}</td><td className="n num">{money(r.end)}</td><td className="n num">{r.excess ? money(r.excess) : ''}</td><td className="small">{r.source} <span className="chip">{r.status}</span></td></tr>)}</tbody></table>
    <h2>Ridgeline — capital account</h2><pre className="page small">{JSON.stringify(d.ridgeline, null, 1)}</pre>
    <h2>IRA basis (Form 8606)</h2><pre className="page small">{JSON.stringify(d.ira, null, 1)}</pre>
    <h2>Home</h2><pre className="page small">{JSON.stringify(d.home, null, 1)}</pre>
  </div>
}

function Carry() {
  const [d] = useLoad<Any>('/api/schedules/carryovers')
  if (!d) return <div className="empty">Loading…</div>
  const keys = Array.from(new Set([...Object.keys(d.in), ...Object.keys(d.out.federal)])).filter(k => !['california', 'sources'].includes(k))
  return <div><table className="t card"><thead><tr><th>Carryover</th><th className="n">Into 2025 (from 2024)</th><th className="n">Out to 2026 (engine)</th><th>Workpaper note</th></tr></thead><tbody>
    {keys.map(k => <tr key={k}><td>{k.replace(/_/g, ' ')}</td><td className="n num">{fmtVal(d.in[k])}</td><td className="n num">{fmtVal(d.out.federal[k])}</td><td className="small">{d.notes[k]}</td></tr>)}</tbody></table>
    <h3>Agreed to prior year</h3><div className="row">{Object.entries(d.verified).map(([k, v]: Any) => <span key={k} className={'chip ' + (v ? 'ok' : 'warn')}>{v ? '✓' : '○'} <Ref r={{ type: 'line', id: k }} /></span>)}</div>
    <h3>California</h3><pre className="page small">{JSON.stringify({ in: d.in.california, out: d.out.california }, null, 1)}</pre></div>
}

function StateSplit() {
  const [d] = useLoad<Any>('/api/schedules/state-split')
  if (!d) return <div className="empty">Loading…</div>
  return <div>
    <p className="small">Residency: {d.residency.map((r: Any) => `${r.state} ${r.from} → ${r.to}`).join(' · ')} ({d.resident_days}/{d.year_days} days in California). 540NR ratio {d.ratio}.</p>
    <table className="t card"><thead><tr><th>Schedule CA (540NR)</th><th className="n">A Federal</th><th className="n">B Subtract</th><th className="n">C Add</th><th className="n">D CA law</th><th className="n">E CA source</th><th>E method</th></tr></thead><tbody>
      {d.rows.map((r: Any) => <tr key={r.line}><td>{r.line}. {r.label}</td><td className="n num">{fmtVal(r.A)}</td><td className="n num">{fmtVal(r.B)}</td><td className="n num">{fmtVal(r.C)}</td><td className="n num">{fmtVal(r.D)}</td><td className="n">{r.E !== null && r.E !== undefined ? <Num k={`SchCA540NR.${r.line}.E`} v={r.E} adj={r.E_adjusted} /> : '—'}</td><td className="small muted">{r.E_rule_text}</td></tr>)}</tbody></table>
    <h2>Wages by work location</h2>
    <table className="t card"><thead><tr><th>Employer</th><th className="n">Box 1</th><th className="n">Box 16 (CA)</th><th>Work location</th><th className="n">CA-source (correct)</th></tr></thead><tbody>
      {d.wage_detail.map((w: Any) => <tr key={w.employer}><td>{w.employer}</td><td className="n num">{money(w.box1)}</td><td className="n num">{money(w.box16_CA)}</td><td className="small">{w.work_location}</td><td className="n num">{money(w.ca_source_correct)}</td></tr>)}</tbody></table>
    <p className="small">Ridgeline apportionment: {Object.entries(d.ridgeline).map(([k, v]: Any) => `${k.replace('pct_', '')} ${Math.round(v * 100)}%`).join(', ')} (D38).</p>
  </div>
}

function Payments() {
  const [d] = useLoad<Any>('/api/schedules/payments')
  if (!d) return <div className="empty">Loading…</div>
  return <div className="grid g2">
    <div className="card"><h2 style={{ marginTop: 0 }}>Federal</h2><div className="fld"><div>Withholding</div><div className="num">{money(d.federal.return.withholding)}</div><div>Estimates (engine)</div><div className="num">{money(d.federal.return.estimates)} → workpaper {money(d.federal.return.estimates_adjusted)}</div><div>Extension (4868)</div><div className="num">{money(d.federal.return.extension)}</div><div>Excess SS</div><div className="num">{money(d.federal.return.excess_ss)}</div></div>
      <h3>IRS account transcript</h3>{d.federal.transcripts.map((t: Any) => <div key={t.as_of}><div className="small muted">as of {t.as_of}</div><table className="t small"><tbody>{t.transactions.map((x: Any, i: number) => <tr key={i}><td className="num">{x.date}</td><td>{x.code}</td><td>{x.description}</td><td className="n num">{fmtVal(x.amount)}</td></tr>)}</tbody></table></div>)}</div>
    <div className="card"><h2 style={{ marginTop: 0 }}>California</h2><div className="fld"><div>Withholding</div><div className="num">{money(d.california.return.withholding)}</div><div>Estimates (engine)</div><div className="num">{money(d.california.return.estimates)} → workpaper {money(d.california.return.estimates_adjusted)}</div></div>
      <h3>FTB account</h3><table className="t small"><tbody>{d.california.ftb.tax_year_2025_payments.map((x: Any, i: number) => <tr key={i}><td className="num">{x.date}</td><td>TY2025</td><td className="n num">{money(x.amount)}</td></tr>)}{d.california.ftb.tax_year_2024_payments_after_filing.map((x: Any, i: number) => <tr key={'b' + i}><td className="num">{x.date}</td><td><span className="chip warn">TY2024</span> {x.note}</td><td className="n num">{money(x.amount)}</td></tr>)}</tbody></table>
      <h3>Extension estimate (from v2)</h3><pre className="page small">{JSON.stringify(d.extension, null, 1)}</pre></div>
  </div>
}

function Prior() {
  const [d] = useLoad<Any>('/api/schedules/prior-year')
  if (!d) return <div className="empty">Loading…</div>
  return <div>
    <table className="t card"><thead><tr><th>Topic</th><th>Prior preparer (2024)</th><th>This year</th><th>Evidence</th></tr></thead><tbody>
      {d.did_vs_changed.map((r: Any) => <tr key={r.topic}><td><b>{r.topic}</b></td><td className="small">{r.prior}</td><td className="small">{r.now}</td><td className="small">{r.evidence}</td></tr>)}</tbody></table>
    <h2>Prior preparer's open items</h2><ul>{d.workpaper.open_items_left_by_prior_preparer.map((x: string) => <li key={x}>{x}</li>)}</ul>
    <h2>Prior preparer's notes</h2><ul>{d.workpaper.notes.map((x: string) => <li key={x} className="small">{x}</li>)}</ul>
  </div>
}
