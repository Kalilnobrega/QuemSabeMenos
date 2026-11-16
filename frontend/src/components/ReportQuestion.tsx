import { createContext, useContext, useState, type ReactNode } from 'react'
import { playSound } from '../lib/sounds'
import type { ReportQuestionRequest } from '../types/events'
import { Sheet } from './Sheet'

type Reason = ReportQuestionRequest['reason']
type Send = (text: string, reason: Reason, comment: string) => Promise<string | null>

const REASONS: { id: Reason; label: string }[] = [
  { id: 'wrong_answer', label: 'A resposta está errada' },
  { id: 'confusing', label: 'A pergunta está confusa' },
  { id: 'wrong_level', label: 'O nível não combina' },
  { id: 'other', label: 'Outra coisa' },
]
const COMMENT_MAX_LENGTH = 300

interface Reports {
  open: (text: string) => void
  reported: (text: string) => boolean
}

const ReportsContext = createContext<Reports | null>(null)

/** O painel do report mora aqui, acima das telas da partida, para não fechar quando a revelação acaba. */
export function ReportProvider({ onSend, children }: { onSend: Send; children: ReactNode }) {
  const [text, setText] = useState<string | null>(null)
  const [sent, setSent] = useState<string[]>([])

  return (
    <ReportsContext.Provider value={{ open: setText, reported: (t) => sent.includes(t) }}>
      {children}
      {text && (
        <ReportSheet
          text={text}
          onSend={onSend}
          onSent={() => {
            setSent((done) => [...done, text])
            setText(null)
          }}
          onClose={() => setText(null)}
        />
      )}
    </ReportsContext.Provider>
  )
}

function FlagIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M5 2.5a1 1 0 0 1 1 1V4h11.4a1 1 0 0 1 .8 1.6L15.9 9l2.3 3.4a1 1 0 0 1-.8 1.6H6v6.5a1 1 0 1 1-2 0v-17a1 1 0 0 1 1-1z" />
    </svg>
  )
}

/** Fica no canto do "Você sabia?": quem achou a pergunta estranha avisa para ela ser arrumada. */
export function ReportButton({ text }: { text: string }) {
  const reports = useContext(ReportsContext)
  if (!reports) return null
  if (reports.reported(text)) {
    return <span className="text-xs font-semibold text-steel">Reportada, valeu!</span>
  }
  return (
    <button
      type="button"
      onClick={() => {
        playSound('clickSoft')
        reports.open(text)
      }}
      className="-my-1 flex items-center gap-1 py-1 text-xs font-semibold text-steel hover:text-chalk"
    >
      <FlagIcon className="size-3.5" />
      Reportar
    </button>
  )
}

interface SheetProps {
  text: string
  onSend: Send
  onSent: () => void
  onClose: () => void
}

function ReportSheet({ text, onSend, onSent, onClose }: SheetProps) {
  const [reason, setReason] = useState<Reason | null>(null)
  const [comment, setComment] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = async () => {
    if (!reason || sending) return
    setSending(true)
    const failed = await onSend(text, reason, comment)
    setSending(false)
    if (failed) {
      setError(failed)
      return
    }
    playSound('select')
    onSent()
  }

  return (
    <Sheet labelledBy="report-title" onClose={onClose} stacked>
      <div className="flex flex-col gap-2 text-center">
        <h2 id="report-title" className="font-display text-3xl tracking-wide text-brand">
          O que tem de errado?
        </h2>
        <p className="line-clamp-3 text-sm text-steel">{text}</p>
      </div>

      <div role="radiogroup" aria-labelledby="report-title" className="flex flex-col gap-2">
        {REASONS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={reason === id}
            onClick={() => {
              playSound('clickSoft')
              setReason(id)
            }}
            className={`btn-3d btn-sm rounded-xl px-4 py-3 text-left font-semibold ${
              reason === id ? 'btn-brand is-pressed text-ink' : 'btn-dark text-chalk'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <label className="flex flex-col gap-2">
        <span className="text-sm font-semibold text-steel">Quer contar mais? É opcional.</span>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={COMMENT_MAX_LENGTH}
          rows={3}
          placeholder="Por exemplo, qual seria a resposta certa"
          className="resize-none rounded-xl bg-panel px-4 py-3 placeholder:text-steel focus:outline-2 focus:outline-brand"
        />
      </label>

      {error && (
        <p key={error} className="error-shake text-center text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="button"
        disabled={!reason || sending}
        onClick={() => void send()}
        className="btn-3d btn-brand rounded-xl py-3 font-display text-2xl tracking-wide text-ink disabled:opacity-50"
      >
        {sending ? 'Enviando…' : 'Enviar'}
      </button>
    </Sheet>
  )
}
