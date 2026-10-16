import React, { useEffect, useState } from 'react'
import { useApp } from './lib'

const STEPS: { page: string; arg?: string; title: string; body: React.ReactNode }[] = [
  { page: 'overview', title: 'Welcome — this is the whole return on one page', body: <>The software computed this return; your job is to prove it is right. <b>Engine</b> is what the software computed. <b>Workpaper</b> is engine plus the adjustments your team approved. <b>Ready to file?</b> lists the firm's required steps, checked live. Use <b>Viewing as</b> (top right) to work as preparer, reviewer, partner or client.</> },
  { page: 'findings', title: 'Findings — start here every day', body: <>Checks that read the actual documents, last year's return and IRS/FTB records. Each finding shows its evidence (click the chips) and, when the fix is mechanical, <b>Accept</b> proposes the adjustment for review. Dismissing needs a reason.</> },
  { page: 'return', arg: 'SchC', title: 'Click any number to trace it', body: <>Every number opens a panel: how it was built, the exact field on the source page, whether it was verified, and its history. From there you can <b>Verify</b>, <b>Adjust</b> (the original is always kept), add a <b>Note</b>, <b>Ask</b> the client or a colleague, or <b>Attach</b> evidence. "⟳ recompute" means an input changed and the tax engine must re-run that line.</> },
  { page: 'documents', title: 'Every document lands somewhere — or says why not', body: <>"Landed" documents feed return lines. "Not applied" means the engine marked a document used but no number moved — that is where several errors hid. Open a document to see its page with each extracted field highlighted; red means a blank or low-confidence read.</> },
  { page: 'review', arg: 'signoffs', title: 'Review and sign-off', body: <>Review notes can <b>block filing</b>. Sign-offs are pinned to what you signed: if a number, evidence or finding in that area changes later, the sign-off shows <b>reopened</b>. Nobody can review their own work; tax effects over 1,000 need the partner.</> },
  { page: 'schedules', title: 'The records you expect', body: <>Return vs last year, tax computation, sales detail (282 lots, grouped and reconciled to the broker statements), depreciation, books to tax, state split, basis by year, carryovers and more — every number clickable.</> },
  { page: 'filing', title: 'Filing and after', body: <>Extension, client approval and e-file signature, rejection and fix, acceptance, then the return freezes; changes after that go into an amendment. The IRS letter in 2028 is answered with a one-click record.</> },
]

export function Tour() {
  const { go, role } = useApp()
  const [i, setI] = useState<number | null>(null)
  useEffect(() => {
    const open = () => setI(0)
    window.addEventListener('wp-tour', open)
    let seen = '1'
    try { seen = localStorage.getItem('wp.toured') || '' } catch {}
    if (!seen && role && role !== 'client') setI(0)
    return () => window.removeEventListener('wp-tour', open)
  }, [role])
  useEffect(() => { if (i !== null) go(STEPS[i].page, STEPS[i].arg) }, [i])
  if (i === null) return null
  const s = STEPS[i]
  const done = () => { try { localStorage.setItem('wp.toured', '1') } catch {} setI(null) }
  return <div className="tour">
    <div className="row"><span className="chip acc">Day-one tour · {i + 1}/{STEPS.length}</span><span className="sp" /><button className="btn sm" onClick={done}>Skip</button></div>
    <h2 style={{ margin: '8px 0 6px' }}>{s.title}</h2>
    <p style={{ margin: 0 }}>{s.body}</p>
    <div className="row" style={{ marginTop: 12 }}>
      <button className="btn sm" disabled={i === 0} onClick={() => setI(i - 1)}>Back</button><span className="sp" />
      {i < STEPS.length - 1 ? <button className="btn sm pri" onClick={() => setI(i + 1)}>Next</button> : <button className="btn sm pri" onClick={done}>Start working</button>}
    </div>
  </div>
}

export const startTour = () => window.dispatchEvent(new Event('wp-tour'))
