import React, { useEffect, useState } from 'react'
import { Any, Ref, post, useApp } from './lib'

const SUGGEST = ['Why did Schedule C gross receipts change from the engine number?', 'What is still blocking filing?', 'Summarize the RSU basis problem for the partner.', 'Which documents did the engine mark as used but never apply?']

export const openAsk = (detail: Any = {}) => window.dispatchEvent(new CustomEvent('wp-ask', { detail }))

function Cited({ text, valid }: { text: string; valid: string[] }) {
  const parts = text.split(/(\[[a-z]+:[^\]\s]+\])/g)
  return <div className="ans">{parts.map((p, i) => {
    const m = p.match(/^\[([a-z]+):([^\]\s]+)\]$/)
    if (!m) return <React.Fragment key={i}>{p}</React.Fragment>
    const [, kind, id] = m
    if (!valid.includes(`${kind}:${id}`)) return <span key={i} className="chip err" title="The model cited something that was not in the evidence it was given">unverified source</span>
    if (kind === 'summary') return <span key={i} className="chip">return summary</span>
    if (kind === 'note') return <span key={i} className="chip rev">note</span>
    return <Ref key={i} r={{ type: kind, id }} />
  })}</div>
}

export function AskPanel() {
  const { boot, send, toast, role } = useApp()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('ask')
  const [focus, setFocus] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<Any>(null)
  useEffect(() => {
    const on = (e: Any) => { setOpen(true); setRes(null); setMode(e.detail?.mode || 'ask'); setFocus(e.detail?.focus || null); setQ(e.detail?.question || '') }
    window.addEventListener('wp-ask', on)
    return () => window.removeEventListener('wp-ask', on)
  }, [])
  const [secs, setSecs] = useState(0)
  useEffect(() => { if (!busy) return; setSecs(0); const t = setInterval(() => setSecs(x => x + 1), 1000); return () => clearInterval(t) }, [busy])
  if (!open) return null
  const run = async (question = q, m = mode) => {
    if (!question && m === 'ask') return
    setBusy(true); setRes(null)
    try { setRes(await post('/api/ask', { question, mode: m, focus })) } catch (e: Any) { toast('⚠ Ask failed: ' + e.message) }
    setBusy(false)
  }
  const pick = (s: string) => { setMode('ask'); setQ(s); run(s, 'ask') }
  const target = focus || (res?.citations || []).find((c: string) => c.startsWith('line:') || c.startsWith('finding:') || c.startsWith('doc:')) || 'area:return_summary'
  const draftBody = (res?.answer || '').split(/\nWhy:/)[0].replace(/\[[a-z]+:[^\]\s]+\]/g, '').trim()
  return <div className="ask">
    <div className="hd"><b>✦ Ask the workpaper</b><span className={'chip ' + (boot?.ai ? 'ok' : '')}>{boot?.ai ? `AI on (${boot.ai})` : 'evidence only — no API key'}</span><span className="sp" /><button className="btn sm" onClick={() => setOpen(false)}>Close</button></div>
    <div className="bd">
      <div className="row" style={{ marginBottom: 8 }}>
        <select className="btn sm" value={mode} onChange={e => setMode(e.target.value)}><option value="ask">Ask a question</option><option value="draft_client_question">Draft a client question</option><option value="draft_notice_response">Draft IRS notice response</option></select>
        {focus && <span className="chip acc">about {focus} <a style={{ cursor: 'pointer', marginLeft: 4 }} onClick={() => setFocus(null)}>✕</a></span>}
      </div>
      {!res && !busy && <div className="small muted">Answers come only from this workpaper's evidence, every sentence cites its source, and any citation outside that evidence is flagged. Nothing is saved unless you save it.</div>}
      {!busy && <div className="row" style={{ gap: 6, margin: '8px 0 10px' }}>{SUGGEST.map(s => <button key={s} type="button" className="chip acc" style={{ whiteSpace: 'normal', textAlign: 'left' }} onClick={() => pick(s)}>{s}</button>)}</div>}
      {busy && <div className="muted">Reading the evidence and asking the model… {secs}s{secs > 12 ? ' (the provider is slow or busy; trying a backup model)' : ''}</div>}
      {res && <div>
        <Cited text={res.answer} valid={res.citations} />
        {res.unverified?.length > 0 && <div className="banner warn small" style={{ marginTop: 8 }}>{res.unverified.length} citation(s) were not in the evidence and are marked unverified. Treat those statements as unsupported.</div>}
        <div className="small muted" style={{ marginTop: 8 }}>{res.model ? `Model ${res.model}` : 'Retrieval only'} · {res.evidence.length} evidence items · logged to the timeline</div>
        {role !== 'client' && res.ai_enabled && <div className="row" style={{ marginTop: 8 }}>
          <button className="btn sm" onClick={() => send({ type: 'note.created', payload: { target, kind: 'comment', text: `AI draft (${res.model}), reviewed and saved by me:\n${res.answer}` } }, 'Saved as a note')}>Save as note on {target}</button>
          {mode === 'draft_client_question' && <button className="btn sm pri" onClick={() => send({ type: 'question.asked', payload: { to: 'client', target, text: draftBody } }, 'Question sent to the client')}>Send to client</button>}
        </div>}
      </div>}
    </div>
    <div className="ft"><textarea rows={2} value={q} placeholder={mode === 'draft_notice_response' ? 'Optional: focus the draft (leave empty for the Letter 566 items)' : 'e.g. Why is the California refund bigger than the engine says?'} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run() } }} />
      <button className="btn pri" disabled={busy || (!q && mode === 'ask')} onClick={() => run()}>Ask</button></div>
  </div>
}
