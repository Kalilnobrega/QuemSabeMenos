import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import type { Snapshot } from '../lib/useRoom'
import type { GameView, PlayerView, RoomState } from '../types/events'
import { LeaveButton } from './LeaveButton'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

/** Lâmpada da curiosidade (no lugar do emoji): amarela, com contorno escuro e brilho. */
function BulbIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={className} aria-hidden="true">
      <g stroke="#FFC107" strokeWidth="2" strokeLinecap="round">
        <path d="M14 1.5v2.5M4.5 5.5l1.8 1.8M23.5 5.5l-1.8 1.8M1.5 14h2.5M24 14h2.5" />
      </g>
      <path
        d="M14 6.5a7 7 0 0 0-4.2 12.6c.8.6 1.2 1.3 1.2 2.1h6c0-.8.4-1.5 1.2-2.1A7 7 0 0 0 14 6.5Z"
        fill="#FFC107"
        stroke="#12141B"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M11.5 12a3 3 0 0 1 2.5-2" fill="none" stroke="#FFF3C4" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="10.8" y="21.2" width="6.4" height="4.3" rx="1.4" fill="#9CA3AF" stroke="#12141B" strokeWidth="1.6" />
      <path d="M11.2 23.3h5.6" stroke="#12141B" strokeWidth="1.2" />
    </svg>
  )
}

/** Foguinho da marca (no lugar do emoji), simples para ficar nítido em tamanho pequeno. */
function FlameIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 28" className={className} aria-hidden="true">
      <path
        d="M12 1.5c3 5.5 8.5 8.5 8.5 15A8.5 8.5 0 0 1 3.5 16.5c0-4 2.4-6 3.4-8.5 1.3 2.8 2.6 3.4 3.2 3.4C9.6 7.5 10.4 4.5 12 1.5Z"
        fill="#F97316"
        stroke="#12141B"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M12 12.5c2 3 4.4 4.3 4.4 7.3a4.4 4.4 0 0 1-8.8 0c0-1.8 1-2.8 1.6-4 .7 1.4 1.3 1.7 1.7 1.7-.4-1.9 0-3.4 1.1-5Z" fill="#FFC107" />
    </svg>
  )
}

const DIFFICULTY: Record<string, { label: ReactNode; className: string }> = {
  easy: { label: 'Fácil', className: 'bg-emerald-500/15 text-emerald-300' },
  medium: { label: 'Média', className: 'bg-brand/15 text-brand' },
  hard: { label: 'Difícil', className: 'bg-red-500/15 text-red-300' },
  impossible: {
    label: (
      <span className="flex items-center gap-1">
        <FlameIcon className="size-4" />
        Impossível
      </span>
    ),
    className: 'bg-orange-500/20 text-orange-300',
  },
}

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number) => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

export function Game({ snapshot, playerId, onAnswer, onPlayAgain, onLeave }: Props) {
  const game = snapshot.room.game!
  if (game.phase === 'starting') {
    return <GameStart snapshot={snapshot} />
  }
  if (game.phase === 'level') {
    return <LevelIntro game={game} />
  }
  if (game.phase === 'intro') {
    return <FinalIntro snapshot={snapshot} />
  }
  if (game.phase === 'finished') {
    return <Podium room={snapshot.room} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  }
  // key: cada rodada começa com a escolha local zerada.
  return <Round key={game.round} snapshot={snapshot} game={game} playerId={playerId} onAnswer={onAnswer} />
}

const LEVEL_TRACK: { key: string; label: ReactNode }[] = [
  { key: 'easy', label: 'Fácil' },
  { key: 'medium', label: 'Média' },
  { key: 'hard', label: 'Difícil' },
  { key: 'impossible', label: <FlameIcon className="size-3.5" /> },
]

const LEVEL_INTRO: Record<string, { title: string; color: string; marker: string; shadow: string; line: string }> = {
  medium: {
    title: 'Média',
    color: 'text-brand',
    marker: 'bg-brand',
    shadow: '#7a5a00',
    line: 'Agora as perguntas valem mais QI.',
  },
  hard: {
    title: 'Difícil',
    color: 'text-red-300',
    marker: 'bg-red-400',
    shadow: '#7f1d1d',
    line: 'Valem muito QI, e errar quase não tira pontos.',
  },
}

/** Apresentação rápida quando a dificuldade muda: a trilha de níveis e o nome do novo nível. */
function LevelIntro({ game }: { game: GameView }) {
  const info = LEVEL_INTRO[game.difficulty] ?? LEVEL_INTRO.medium
  const current = LEVEL_TRACK.findIndex((level) => level.key === game.difficulty)
  const trackRef = useRef<HTMLOListElement>(null)
  const markerRef = useRef<HTMLSpanElement>(null)

  // O destaque colorido nasce em cima do nível anterior e pula, em arco, até o novo.
  useLayoutEffect(() => {
    const track = trackRef.current
    const marker = markerRef.current
    if (!track || !marker) return
    const items = [...track.querySelectorAll('li')] as HTMLElement[]
    const target = items[current]
    const from = items[current - 1]
    Object.assign(marker.style, {
      left: `${target.offsetLeft}px`,
      top: `${target.offsetTop}px`,
      width: `${target.offsetWidth}px`,
      height: `${target.offsetHeight}px`,
    })
    if (!from || reducedMotion()) return
    const dx = from.offsetLeft - target.offsetLeft
    const scale = from.offsetWidth / target.offsetWidth
    marker.animate(
      [
        { transform: `translateX(${dx}px) scaleX(${scale})` },
        { transform: `translateX(${dx / 2}px) translateY(-16px) scale(1.15)`, offset: 0.5 },
        { transform: 'translateY(2px) scale(1.05, 0.9)', offset: 0.85 },
        { transform: 'none' },
      ],
      { duration: 650, delay: 450, easing: 'ease-in-out', fill: 'backwards' },
    )
  }, [current])

  return (
    <section className="flex min-h-[60dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">Próximo nível</p>
      <ol ref={trackRef} className="intro-step relative flex items-center gap-1.5" aria-label="Níveis da partida">
        <span ref={markerRef} className={`absolute rounded-full ${info.marker}`} style={{ transformOrigin: 'left center' }} aria-hidden="true" />
        {LEVEL_TRACK.map((level, index) => (
          <li
            key={level.key}
            className={`relative rounded-full px-3 py-1 text-xs font-semibold ${
              index === current ? 'level-land text-ink' : index < current ? 'bg-panel text-steel line-through' : 'bg-panel text-steel'
            }`}
          >
            {level.label}
          </li>
        ))}
      </ol>
      <h1 className={`intro-slam font-display text-6xl ${info.color}`} style={{ textShadow: `0 4px 0 ${info.shadow}` }}>
        {info.title}
      </h1>
      <p className="intro-step font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.7s' }}>
        {info.line}
      </p>
    </section>
  )
}

/** Contagem antes da 1ª pergunta: "Prepare-se!", a escalação dos jogadores e uma dica. */
function GameStart({ snapshot }: { snapshot: Snapshot }) {
  const { room, receivedAt } = snapshot
  const game = room.game!
  const now = useNow(true)
  const remaining = Math.max(0, receivedAt + game.phase_ends_in_ms - now)
  const count = Math.ceil(remaining / 1000)

  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">A partida vai começar</p>
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Prepare-se!</h1>
      <p className="intro-step font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        {game.total_rounds} perguntas · {room.settings.answer_seconds} segundos cada
      </p>
      <ul className="flex max-w-xs flex-wrap justify-center gap-2" aria-label="Jogadores">
        {room.players.map((player, index) => (
          <li key={player.id} className="avatar-pop" style={{ animationDelay: `${0.8 + index * 0.08}s` }}>
            <img src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-12" />
          </li>
        ))}
      </ul>
      <div className="flex h-20 items-center" aria-live="polite">
        {count <= 3 && count > 0 && (
          <span key={count} className="intro-count font-display text-7xl text-chalk">
            {count}
          </span>
        )}
      </div>
    </section>
  )
}

/** Tela de preparação antes da pergunta final: chama, "Impossível!" e contagem regressiva. */
function FinalIntro({ snapshot }: { snapshot: Snapshot }) {
  const game = snapshot.room.game!
  const now = useNow(true)
  const remaining = Math.max(0, snapshot.receivedAt + game.phase_ends_in_ms - now)
  const count = Math.ceil(remaining / 1000)

  return (
    <section className="final-intro relative isolate flex min-h-[72dvh] w-full flex-col items-center justify-center gap-3 overflow-hidden rounded-3xl px-4 text-center">
      <div className="final-intro-glow absolute inset-0 -z-10" aria-hidden="true" />
      <Flame />
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-orange-200 uppercase">Pergunta final</p>
      <h1 className="intro-slam font-display text-6xl text-orange-300 [text-shadow:0_4px_0_#7c2d12]">Impossível!</h1>
      <p className="intro-step intro-step-late max-w-xs font-hand text-lg font-medium text-chalk">
        Vale 35 de QI, e errar não tira pontos.
      </p>
      <div className="flex h-20 items-center" aria-live="polite">
        {count <= 3 && count > 0 && (
          <span key={count} className="intro-count font-display text-7xl text-chalk">
            {count}
          </span>
        )}
      </div>
    </section>
  )
}

function Flame() {
  return (
    <svg viewBox="0 0 100 104" className="intro-flame h-36 w-36" aria-hidden="true">
      <defs>
        <linearGradient id="flame-outer" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#DC2626" />
          <stop offset="1" stopColor="#FB923C" />
        </linearGradient>
      </defs>
      <path
        d="M50 4 C62 26 84 40 84 66 C84 86 68 100 50 100 C32 100 16 86 16 66 C16 50 26 42 30 30 C36 44 42 46 44 46 C40 30 44 16 50 4 Z"
        fill="url(#flame-outer)"
        stroke="#12141B"
        strokeWidth="4"
        strokeLinejoin="round"
      />
      <path
        d="M50 44 C58 58 68 64 68 78 C68 90 60 98 50 98 C40 98 32 90 32 78 C32 70 38 66 40 60 C44 68 47 70 48 70 C46 62 46 52 50 44 Z"
        fill="#FFC107"
      />
      <path d="M50 70 C55 78 58 82 58 88 C58 94 54 97 50 97 C46 97 42 94 42 88 C42 82 46 78 50 70 Z" fill="#FFF3C4" />
    </svg>
  )
}

/** Re-renderiza a cada quadro enquanto `active`, para o texto digitando e o cronômetro. */
function useNow(active: boolean) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    if (!active) return
    let frame = requestAnimationFrame(function tick() {
      setNow(performance.now())
      frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [active])
  return now
}

function formatScore(score: number) {
  return score < 0 ? `−${-score}` : `${score}`
}

/** Vibra o celular, quando o navegador permite (no iPhone é ignorado). */
function vibrate(pattern: number | number[]) {
  navigator.vibrate?.(pattern)
}

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

/** Curva que começa devagar, acelera no meio e desacelera no final. */
const easeInOutCubic = (k: number) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2)

/** Número que sobe (ou desce) contando de `from` até `to`, depois de `delay` ms. */
function CountUp({
  from,
  to,
  format = String,
  duration = 1800,
  delay = 400,
}: {
  from: number
  to: number
  format?: (n: number) => string
  duration?: number
  delay?: number
}) {
  const [value, setValue] = useState(reducedMotion() ? to : from)
  useEffect(() => {
    if (reducedMotion()) return
    const start = performance.now() + delay
    let frame = requestAnimationFrame(function tick(t) {
      const k = Math.min(1, Math.max(0, (t - start) / duration))
      setValue(Math.round(from + (to - from) * easeInOutCubic(k)))
      if (k < 1) frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [from, to, duration, delay])
  return <>{format(value)}</>
}

/** Mais QI primeiro; no empate, quem respondeu mais rápido na soma da partida. */
function byRanking(a: PlayerView, b: PlayerView) {
  return b.score - a.score || a.answer_ms - b.answer_ms
}

function formatDelta(delta: number) {
  return delta > 0 ? `+${delta}` : formatScore(delta)
}

interface RoundProps {
  snapshot: Snapshot
  game: GameView
  playerId: string | null
  onAnswer: (option: number) => Promise<string | null>
}

function Round({ snapshot, game, playerId, onAnswer }: RoundProps) {
  const { room, receivedAt } = snapshot
  const [choice, setChoice] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const timed = game.phase !== 'finished'
  const now = useNow(timed)
  const remaining = Math.max(0, receivedAt + game.phase_ends_in_ms - now)
  const progress = game.phase_duration_ms > 0 ? 1 - remaining / game.phase_duration_ms : 1

  // Na resposta, a barra fica cheia e dourada durante a carência (pontos máximos)
  // e depois esvazia até o fim do tempo, junto com os pontos.
  const graceMs = room.settings.speed_grace_seconds * 1000
  const inGrace = game.phase === 'answering' && game.phase_duration_ms - remaining < graceMs
  const barFill =
    game.phase === 'answering'
      ? inGrace
        ? 1
        : remaining / Math.max(1, game.phase_duration_ms - graceMs)
      : 1 - progress

  const question = game.question!
  const typing = game.phase === 'reading'
  const text = typing ? question.text.slice(0, Math.ceil(question.text.length * progress)) : question.text
  const answered = choice !== null || (playerId !== null && game.answered.includes(playerId))
  const canAnswer = game.phase === 'answering' && !answered
  const showResults = game.phase === 'results'
  const myResult = game.results.find((r) => r.player_id === playerId)
  const connectedCount = room.players.filter((p) => p.connected).length
  const difficulty = DIFFICULTY[question.difficulty]
  const secondsLeft = Math.ceil(remaining / 1000)
  const urgent = game.phase === 'answering' && remaining < 3000

  // Vibra a cada um dos 3 últimos segundos, só para quem ainda não respondeu.
  useEffect(() => {
    if (urgent && !answered && secondsLeft > 0) vibrate(25)
  }, [urgent, answered, secondsLeft])

  // Vibração diferente para acerto e erro, quando a resposta é revelada.
  useEffect(() => {
    if (!showResults || !myResult || myResult.option === null) return
    vibrate(myResult.correct ? 40 : [70, 50, 70])
  }, [showResults, myResult])

  const pick = async (option: number) => {
    if (!canAnswer) return
    setChoice(option)
    const failure = await onAnswer(option)
    if (failure) {
      setChoice(null)
      setError(failure)
    }
  }

  const optionClass = (index: number) => {
    const chosen = choice === index || myResult?.option === index
    if (showResults) {
      if (index === game.correct_option) return 'reveal-pop btn-correct text-white'
      if (chosen) return 'reveal-shake btn-wrong is-pressed text-white'
      return 'btn-dark opacity-40'
    }
    if (chosen) return 'btn-dark is-pressed outline-2 outline-brand'
    if (!canAnswer) return 'btn-dark opacity-50'
    return 'btn-dark'
  }

  return (
    <section className="flex w-full flex-col gap-5">
      <header className="flex items-center justify-between gap-2 text-sm">
        <span className="font-semibold text-steel">
          Pergunta {game.round}/{game.total_rounds}
        </span>
        <span className="flex gap-2">
          <span className="rounded-full bg-panel px-3 py-1 text-steel">{question.theme}</span>
          <span className={`round-chip rounded-full px-3 py-1 font-semibold ${difficulty.className}`}>{difficulty.label}</span>
        </span>
      </header>

      <div className="flex h-8 items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel">
          {game.phase !== 'reading' && (
            <div
              className={`h-full rounded-full ${
                showResults
                  ? 'bg-steel/60'
                  : inGrace
                    ? 'bg-brand shadow-[0_0_12px_rgba(255,193,7,0.8)]'
                    : remaining < 3000
                      ? 'bg-red-400'
                      : 'bg-amber-200'
              }`}
              style={{ width: `${Math.min(1, Math.max(0, barFill)) * 100}%` }}
            />
          )}
        </div>
        <span
          key={urgent ? secondsLeft : 'calm'}
          className={`w-8 text-right font-display text-2xl tabular-nums ${urgent ? 'timer-urgent text-red-400' : ''}`}
        >
          {game.phase === 'answering' ? secondsLeft : ''}
        </span>
      </div>

      {/* Altura reservada para até 3 linhas: o texto digitando não empurra as alternativas. */}
      <h1 className="round-question min-h-[6.25rem] text-[1.4rem] leading-snug font-bold">
        {text}
        {typing && <span className="ml-0.5 inline-block w-[0.5ch] animate-pulse text-brand">|</span>}
      </h1>

      <div className="grid auto-rows-fr grid-cols-2 gap-3">
        {question.options.map((option, index) => (
          <button
            key={index}
            onClick={() => pick(index)}
            disabled={!canAnswer}
            style={{ animationDelay: `${0.12 + index * 0.06}s` }}
            className={`round-option btn-3d btn-sm flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${optionClass(index)}`}
          >
            <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
            <span className="min-w-0 [overflow-wrap:anywhere]">{option}</span>
          </button>
        ))}
      </div>

      {error && <p className="text-center text-red-300">{error}</p>}

      {showResults ? (
        <RoundSummary room={room} game={game} playerId={playerId} />
      ) : (
        <p className="min-h-7 text-center font-hand font-medium text-lg text-steel">
          {typing
            ? 'Leia com atenção…'
            : answered
              ? `Resposta enviada! Esperando a galera (${game.answered.length}/${connectedCount})`
              : `${game.answered.length}/${connectedCount} já responderam`}
        </p>
      )}
    </section>
  )
}

function RoundSummary({ room, game, playerId }: { room: RoomState; game: GameView; playerId: string | null }) {
  const mine = game.results.find((r) => r.player_id === playerId)
  const deltas = Object.fromEntries(game.results.map((r) => [r.player_id, r.delta]))

  let headline = null
  // A curiosidade vem logo depois do veredito, antes do ranking, para caber na tela do celular.
  if (mine) {
    const verdict = mine.option === null ? 'Não respondeu!' : mine.correct ? 'Acertou!' : 'Errou!'
    headline = (
      <p className="text-center font-display text-3xl tracking-wide">
        <span className={mine.correct ? 'text-emerald-300' : 'text-red-300'}>{verdict}</span>{' '}
        <span className="text-chalk">
          {mine.correct && mine.delta === 0 ? (
            'Não fez mais que a obrigação.'
          ) : (
            <>
              <CountUp from={0} to={mine.delta} format={formatDelta} /> QI
            </>
          )}
        </span>
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {headline}
      {game.fact && (
        <div className="rounded-xl border border-brand/30 bg-brand/10 px-4 py-3">
          <p className="flex items-center gap-1.5 font-display text-lg tracking-wide text-brand">
            <BulbIcon className="size-5" />
            Você sabia?
          </p>
          <p className="mt-1 leading-relaxed">{game.fact}</p>
        </div>
      )}
      <Ranking players={room.players} playerId={playerId} deltas={deltas} />
    </div>
  )
}

interface RankingProps {
  players: PlayerView[]
  playerId: string | null
  deltas?: Record<string, number>
}

function Ranking({ players, playerId, deltas }: RankingProps) {
  const sorted = [...players].sort(byRanking)
  const listRef = useRef<HTMLOListElement>(null)

  // Com os pontos da rodada, começa na ordem de antes e desliza cada um para a posição nova.
  useLayoutEffect(() => {
    const list = listRef.current
    if (!deltas || !list || reducedMotion()) return
    const before = [...players]
      .map((p) => ({ ...p, score: p.score - (deltas[p.id] ?? 0) }))
      .sort(byRanking)
      .map((p) => p.id)
    const items = [...list.children] as HTMLElement[]
    const step = items.length > 1 ? items[1].offsetTop - items[0].offsetTop : 0
    items.forEach((el, index) => {
      const shift = (before.indexOf(el.dataset.id!) - index) * step
      if (!shift) return
      el.animate([{ transform: `translateY(${shift}px)` }, { transform: 'translateY(0)' }], {
        duration: 650,
        delay: 350,
        easing: 'cubic-bezier(.2,.8,.2,1)',
        fill: 'backwards',
      })
    })
    // Só na primeira exibição do ranking desta rodada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <ol ref={listRef} className="flex flex-col gap-2">
      {sorted.map((player, index) => (
        <li
          key={player.id}
          data-id={player.id}
          className={`relative flex items-center gap-3 rounded-xl bg-panel px-3 py-2 ${player.connected ? '' : 'opacity-50'} ${
            player.id === playerId ? 'ring-1 ring-brand/60' : ''
          }`}
        >
          <span className="w-5 text-center font-display text-lg text-steel">{index + 1}</span>
          <img src={AVATAR_URLS[player.avatar]} alt="" className="size-9" />
          <span className="flex-1 truncate font-semibold">{player.nickname}</span>
          {deltas && player.id in deltas && (
            <span className={`text-sm font-semibold ${deltas[player.id] > 0 ? 'text-emerald-300' : deltas[player.id] < 0 ? 'text-red-300' : 'text-steel'}`}>
              {formatDelta(deltas[player.id])}
            </span>
          )}
          <span className="w-16 text-right font-display text-xl tracking-wide text-brand">
            {deltas && player.id in deltas ? (
              <CountUp from={player.score - deltas[player.id]} to={player.score} format={formatScore} delay={700} />
            ) : (
              formatScore(player.score)
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}

interface PodiumProps {
  room: RoomState
  playerId: string | null
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

function Podium({ room, playerId, onPlayAgain, onLeave }: PodiumProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const sorted = [...room.players].sort(byRanking)
  const best = sorted[0]
  const worst = sorted.length > 1 ? sorted[sorted.length - 1] : null
  const isHost = room.host_id === playerId

  return (
    <section className="flex w-full flex-col gap-6">
      <h1 className="text-center font-display text-5xl tracking-wide text-brand">Fim de jogo!</h1>

      <div className="grid grid-cols-2 gap-3">
        {best && <Highlight title="O menos burro" icon={coroa} player={best} tone="text-brand" winner />}
        {worst && <Highlight title="Quem sabe menos" icon={haha} player={worst} tone="text-red-300" />}
      </div>

      <Ranking players={room.players} playerId={playerId} />

      {notice && <p className="text-center text-steel">{notice}</p>}

      {isHost ? (
        <button
          onClick={async () => setNotice(await onPlayAgain())}
          className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink"
        >
          Jogar de novo
        </button>
      ) : (
        <p className="text-center font-hand font-medium text-lg text-steel">Esperando o anfitrião decidir se tem revanche…</p>
      )}

      <LeaveButton onLeave={onLeave} />
    </section>
  )
}

const CONFETTI_COLORS = ['#FFC107', '#F8FAFC', '#34D399', '#F87171', '#60A5FA', '#FB923C']

/** Confete caindo sobre o cartão do vencedor. Posições fixas por índice (sem aleatório a cada render). */
function Confetti() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl" aria-hidden="true">
      {Array.from({ length: 28 }, (_, i) => (
        <span
          key={i}
          className="confetti"
          style={{
            left: `${(i * 37) % 100}%`,
            background: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
            animationDelay: `${(i % 7) * 0.18}s`,
            animationDuration: `${1.8 + (i % 5) * 0.25}s`,
            transform: `rotate(${i * 47}deg)`,
          }}
        />
      ))}
    </div>
  )
}

function Highlight({ title, icon, player, tone, winner = false }: { title: string; icon: string; player: PlayerView; tone: string; winner?: boolean }) {
  return (
    <div className="podium-card relative flex flex-col items-center gap-2 rounded-2xl bg-panel p-4 text-center">
      {winner && <Confetti />}
      <span className={`font-display text-lg tracking-wide ${tone}`}>{title}</span>
      <div className="relative">
        <img src={AVATAR_URLS[player.avatar]} alt="" className="size-20" />
        <img src={icon} alt="" className={`absolute -top-4 -right-6 size-11 ${winner ? 'icon-bounce' : 'icon-wobble'}`} />
      </div>
      <span className="w-full truncate text-lg font-bold">{player.nickname}</span>
      <span className="font-display text-2xl text-brand">{formatScore(player.score)} QI</span>
    </div>
  )
}
