import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { playSound } from '../lib/sounds'
import type { ReportQuestionRequest } from '../types/events'
import { Sheet } from './Sheet'

type Reason = ReportQuestionRequest['reason']
type Send = (text: string, reason: Reason, comment: string) => Promise<string | null>
type Status = 'idle' | 'marked' | 'detailed'

const REASONS: { id: Reason; label: string }[] = [
  { id: 'wrong_answer', label: 'A resposta está errada' },
  { id: 'confusing', label: 'A pergunta está confusa' },
  { id: 'wrong_level', label: 'O nível não combina' },
  { id: 'other', label: 'Outra coisa' },
]
const COMMENT_MAX_LENGTH = 300
const NOTICE_MS = 3000
const MARKED_NOTICE = 'Marcada! No fim da partida você conta o que houve.'
const SENT_NOTICE = 'Valeu! Vamos conferir essa pergunta.'

interface Reports {
  /** As perguntas que este jogador viu na revelação, na ordem. */
  seen: string[]
  marked: string[]
  status: (text: string) => Status
  register: (text: string) => void
  /** Um toque na revelação: o servidor já guarda, sem motivo, e ninguém espera. */
  mark: (text: string) => Promise<void>
  /** Abre o painel para contar o motivo, sem pressa. */
  detail: (text: string) => void
}

const ReportsContext = createContext<Reports | null>(null)

interface ProviderProps {
  onSend: Send
  /** Uma partida nova começa com a lista vazia. */
  playing: boolean
  children: ReactNode
}

/** Guarda as perguntas da partida e o painel do report, acima das telas, para nada fechar com a revelação. */
export function ReportProvider({ onSend, playing, children }: ProviderProps) {
  const [seen, setSeen] = useState<string[]>([])
  const [marked, setMarked] = useState<string[]>([])
  const [detailed, setDetailed] = useState<string[]>([])
  const [sheet, setSheet] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ key: number; text: string } | null>(null)

  const [wasPlaying, setWasPlaying] = useState(playing)
  if (playing !== wasPlaying) {
    setWasPlaying(playing)
    if (playing) {
      setSeen([])
      setMarked([])
      setDetailed([])
    }
  }

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), NOTICE_MS)
    return () => clearTimeout(timer)
  }, [notice])

  const show = (text: string) => setNotice({ key: Date.now(), text })
  const reports: Reports = {
    seen,
    marked,
    status: (text) => (detailed.includes(text) ? 'detailed' : marked.includes(text) ? 'marked' : 'idle'),
    register: (text) => setSeen((list) => (list.includes(text) ? list : [...list, text])),
    mark: async (text) => {
      const failed = await onSend(text, 'unspecified', '')
      if (failed) {
        show(failed)
        return
      }
      setMarked((list) => (list.includes(text) ? list : [...list, text]))
      show(MARKED_NOTICE)
    },
    detail: setSheet,
  }

  return (
    <ReportsContext.Provider value={reports}>
      {children}
      {sheet && (
        <ReportSheet
          text={sheet}
          onSend={onSend}
          onSent={() => {
            setDetailed((list) => [...list, sheet])
            setSheet(null)
            show(SENT_NOTICE)
          }}
          onClose={() => setSheet(null)}
        />
      )}
      {/* O aviso aparece mesmo se a revelação já acabou e o botão sumiu da tela. */}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 top-4 z-50 flex justify-center px-4"
      >
        {notice && (
          <p
            key={notice.key}
            className="notice-in flex items-center gap-2 rounded-full border border-brand/40 bg-ink px-4 py-2 text-sm font-semibold text-chalk shadow-lg"
          >
            <FlagIcon className="size-4 shrink-0 text-brand" />
            {notice.text}
          </p>
        )}
      </div>
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

/** Fica no canto do "Você sabia?": um toque marca a pergunta, e o motivo fica para o fim da partida. */
export function ReportButton({ text }: { text: string }) {
  const reports = useContext(ReportsContext)
  const [busy, setBusy] = useState(false)
  const register = reports?.register

  useEffect(() => {
    register?.(text)
    // Só quando a pergunta muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])

  if (!reports) return null
  if (reports.status(text) !== 'idle') {
    return (
      <span className="flex items-center gap-1 text-xs font-semibold text-brand">
        <FlagIcon className="size-3.5" />
        Marcada
      </span>
    )
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        playSound('clickSoft')
        setBusy(true)
        await reports.mark(text)
        setBusy(false)
      }}
      className="-my-1 flex items-center gap-1 py-1 text-xs font-semibold text-steel hover:text-chalk disabled:opacity-50"
    >
      <FlagIcon className="size-3.5" />
      Reportar
    </button>
  )
}

/** No fim de jogo: as perguntas marcadas pedem o motivo, e dá para reportar qualquer outra da partida. */
export function MatchQuestions() {
  const reports = useContext(ReportsContext)
  const [open, setOpen] = useState(false)
  if (!reports || reports.seen.length === 0) return null
  const pending = reports.marked.filter((text) => reports.status(text) === 'marked')

  const row = (text: string) => {
    const status = reports.status(text)
    return (
      <li key={text} className="flex items-center gap-3 border-t border-white/5 py-2 first:border-t-0">
        <p className="line-clamp-2 flex-1 text-sm">{text}</p>
        {status === 'detailed' ? (
          <span className="shrink-0 text-xs font-semibold text-success">Enviado</span>
        ) : (
          <button
            type="button"
            onClick={() => {
              playSound('clickSoft')
              reports.detail(text)
            }}
            className={`btn-3d btn-sm shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold ${
              status === 'marked' ? 'btn-brand text-ink' : 'btn-dark text-steel hover:text-chalk'
            }`}
          >
            {status === 'marked' ? 'Contar' : 'Reportar'}
          </button>
        )}
      </li>
    )
  }

  return (
    <section className="flex flex-col gap-2 rounded-xl border border-white/10 bg-panel/60 p-4">
      {pending.length > 0 && (
        <>
          <h2 className="flex items-center gap-1.5 font-display text-xl tracking-wide text-brand">
            <FlagIcon className="size-5" />
            {pending.length === 1 ? 'Você marcou 1 pergunta' : `Você marcou ${pending.length} perguntas`}
          </h2>
          <p className="text-sm text-steel">Conta o que tem de errado para a gente arrumar.</p>
          <ul>{pending.map(row)}</ul>
        </>
      )}
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          playSound('clickSoft')
          setOpen(!open)
        }}
        className="py-1 text-left text-sm font-semibold text-steel underline underline-offset-2 hover:text-chalk"
      >
        {open ? 'Esconder as perguntas da partida' : `Ver as ${reports.seen.length} perguntas da partida`}
      </button>
      {open && <ul>{reports.seen.map(row)}</ul>}
    </section>
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
