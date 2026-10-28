import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { POWERUP_INFO, gainLabel, scrambleWords } from '../lib/powerups'
import { playSound, type SoundId } from '../lib/sounds'
import { reducedMotion, useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import type { Snapshot } from '../lib/useRoom'
import type { Bonus, DuelView, GameView, PlayerView, PowerUpUse, RoomState, RoundResult } from '../types/events'
import { LeaveButton } from './LeaveButton'
import { ActivePowerUps, InstantPowerUps, Magnifier, PowerUpBar, PowerUpIcon, ScratchCard } from './PowerUps'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

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

function SnowflakeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" strokeLinecap="round" aria-hidden="true">
      <g stroke="#12141B" strokeWidth="5">
        <path d="M12 2.5v19M3.8 7.2l16.4 9.6M3.8 16.8l16.4-9.6" />
      </g>
      <g stroke="#7DD3FC" strokeWidth="2.6">
        <path d="M12 2.5v19M3.8 7.2l16.4 9.6M3.8 16.8l16.4-9.6" />
        <path d="M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5" />
      </g>
    </svg>
  )
}

function StarIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        d="m12 2.8 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.6l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8L12 2.8Z"
        fill="#FFC107"
        stroke="#12141B"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  )
}

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
  onBet: (amount: number) => Promise<string | null>
  onDuelBet: (choice: string) => Promise<string | null>
  onArm: (kind: PowerUpUse['kind'], target: string | null, legendary?: boolean, theme?: string | null) => Promise<string | null>
  onUse: (kind: PowerUpUse['kind']) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

export function Game({ snapshot, playerId, onAnswer, onBet, onDuelBet, onArm, onUse, onSkip, onPlayAgain, onLeave }: Props) {
  const game = snapshot.room.game!
  if (game.duel) {
    return (
      <DuelScreen
        key={`${game.duel.challenger}-${game.duel.rival}`}
        snapshot={snapshot}
        stage={{ duel: game.duel, phase: game.phase, phase_ends_in_ms: game.phase_ends_in_ms, phase_duration_ms: game.phase_duration_ms }}
        playerId={playerId}
        onAnswer={onAnswer}
        onDuelBet={onDuelBet}
      />
    )
  }
  if (game.phase === 'starting') {
    return <GameStart snapshot={snapshot} />
  }
  if (game.phase === 'level') {
    return <LevelIntro game={game} />
  }
  if (game.phase === 'intro') {
    return <FinalIntro snapshot={snapshot} />
  }
  if (game.phase === 'betting') {
    return <Betting snapshot={snapshot} playerId={playerId} onBet={onBet} />
  }
  if (game.phase === 'finished') {
    return <Podium room={snapshot.room} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  }
  // key: cada rodada começa com a escolha local zerada.
  return <Round key={game.round} snapshot={snapshot} game={game} playerId={playerId} onAnswer={onAnswer} onArm={onArm} onUse={onUse} onSkip={onSkip} />
}

const DUEL_INTRO_MS = 2800
const DUEL_KIND: Record<string, string> = { true_false: 'Verdadeiro ou falso', hard: 'Difícil', impossible: 'Impossível' }

/** O X1 em andamento e o relógio da fase: vem do clássico ou dos Times. */
export interface DuelStage {
  duel: DuelView
  phase: string
  phase_ends_in_ms: number
  phase_duration_ms: number
}

interface DuelScreenProps {
  snapshot: Snapshot
  stage: DuelStage
  playerId: string | null
  onAnswer: Props['onAnswer']
  onDuelBet: Props['onDuelBet']
  side?: (id: string) => string // Times: de que time é cada duelista
}

/** X1: a partida para e todo mundo assiste. A plateia aposta, os dois respondem, e no fim o acerto de contas. */
export function DuelScreen({ snapshot, stage, playerId, onAnswer, onDuelBet, side }: DuelScreenProps) {
  const { room, receivedAt } = snapshot
  const game = stage
  const duel = stage.duel
  const [error, setError] = useState<string | null>(null)
  const now = useNow(game.phase !== 'duel_end')
  const remaining = Math.max(0, receivedAt + game.phase_ends_in_ms - now)
  const fighters = [duel.challenger, duel.rival].map((id) => room.players.find((p) => p.id === id))
  const nick = (id: string | null | undefined) => (id === playerId ? 'Você' : (room.players.find((p) => p.id === id)?.nickname ?? '?'))
  const name = (id: string | null | undefined) => (side && id ? `${nick(id)} (${side(id)})` : nick(id))
  const fighting = playerId === duel.challenger || playerId === duel.rival
  const [intro, setIntro] = useState<'on' | 'leaving' | 'off'>(() => (reducedMotion() ? 'off' : 'on'))
  useSoundsOnMount([['impossible', 0], ['duelIntro', 850], ['duelFight', 1650]])
  useEffect(() => {
    if (intro === 'off') return
    vibrate([0, 950, 120])
    const leave = setTimeout(() => setIntro('leaving'), DUEL_INTRO_MS - 350)
    const done = setTimeout(() => setIntro('off'), DUEL_INTRO_MS)
    return () => {
      clearTimeout(leave)
      clearTimeout(done)
    }
    // Só uma vez, quando o duelo aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (game.phase === 'duel_answering') playSound(duel.kind === 'impossible' ? 'duelLastQuestion' : 'answersOpen')
    if (game.phase === 'duel_end') playSound(duel.winner === playerId ? 'duelWin' : duel.loser === playerId ? 'duelLose' : 'duelWatch')
  }, [game.phase, duel.question_number, duel.kind, duel.winner, duel.loser, playerId])

  const bet = async (choice: string) => {
    playSound('duelBet')
    setError(await onDuelBet(choice))
  }

  let body: ReactNode
  if (game.phase === 'duel_betting') {
    body = (
      <div className="flex flex-col items-center gap-3 text-center">
        <p className="font-display text-3xl tracking-wide text-brand">Façam suas apostas!</p>
        {duel.can_bet ? (
          <>
            <p className="text-steel">5 de QI em quem ganha. Acertou, recebe 10. Em {Math.ceil(remaining / 1000)}s, sorteamos para quem não escolher.</p>
            <div className="grid w-full grid-cols-2 gap-3">
              {fighters.map((p) =>
                p ? (
                  <button key={p.id} onClick={() => void bet(p.id)} className="btn-3d btn-dark flex flex-col items-center gap-1 rounded-xl py-3 font-semibold">
                    <img src={AVATAR_URLS[p.avatar]} alt="" className="size-12" />
                    Apostar em {p.nickname}
                  </button>
                ) : null,
              )}
            </div>
          </>
        ) : (
          <p className="font-hand text-lg font-medium text-chalk">
            {duel.my_bet ? `Você apostou 5 de QI em ${name(duel.my_bet)}.` : fighting ? 'A plateia está apostando em quem ganha…' : 'Sem QI para apostar. Só assiste!'}
          </p>
        )}
      </div>
    )
  } else if (game.phase === 'duel_end') {
    const myBet = duel.bets[playerId ?? '']
    body = (
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="font-display text-4xl tracking-wide text-brand">{duel.winner === playerId ? 'Você venceu o X1!' : `${name(duel.winner)} venceu o X1!`}</p>
        <ul className="flex w-full flex-col gap-1.5 font-semibold">
          <li className="rounded-xl bg-red-500/15 px-3 py-1.5 text-red-200">{name(duel.loser)} pagou {duel.paid} de QI (40%)</li>
          {duel.from_bets > 0 && <li className="rounded-xl bg-emerald-500/15 px-3 py-1.5 text-emerald-200">+{duel.from_bets} de quem apostou contra {name(duel.winner) === 'Você' ? 'você' : name(duel.winner)}</li>}
          {duel.favorite_bonus > 0 && <li className="rounded-xl bg-brand/15 px-3 py-1.5 text-brand">+{duel.favorite_bonus} de bônus de favorito da torcida</li>}
          {myBet && <li className={`rounded-xl px-3 py-1.5 ${myBet === duel.winner ? 'bg-emerald-500/15 text-emerald-200' : 'bg-red-500/15 text-red-200'}`}>Sua aposta em {name(myBet) === 'Você' ? 'você' : name(myBet)}: {myBet === duel.winner ? '+5' : '−5'}</li>}
        </ul>
      </div>
    )
  } else {
    body = <DuelQuestionView key={duel.question_number} snapshot={snapshot} stage={stage} playerId={playerId} remaining={remaining} onAnswer={async (option) => setError(await onAnswer(option))} />
  }

  if (intro !== 'off') {
    return (
      <div className={`duel-intro ${intro === 'leaving' ? 'duel-out' : ''}`} aria-label="X1!">
        <div className="relative flex items-center justify-center">
          <span className="duel-burst" />
          <PowerUpIcon kind="duel" className="duel-clash relative size-28" />
        </div>
        <p className="intro-slam font-display text-7xl text-brand [text-shadow:0_5px_0_#7a5a00] [animation-delay:1.1s]">X1!</p>
        <div className="flex w-full max-w-sm items-center justify-between px-6">
          {fighters.map((p, i) =>
            p ? (
              <div key={p.id} className={`flex flex-col items-center gap-1 ${i === 0 ? 'duel-in-left' : 'duel-in-right'}`}>
                <img src={AVATAR_URLS[p.avatar]} alt="" className="size-20" />
                <span className="max-w-32 truncate font-display text-2xl tracking-wide text-chalk">{p.id === playerId ? 'Você' : p.nickname}</span>
              </div>
            ) : null,
          )}
        </div>
      </div>
    )
  }

  return (
    <section className="flex w-full flex-col gap-5">
      <header className="flex flex-col items-center gap-1 text-center">
        <p className="font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">X1!</p>
        {duel.question_number > 0 && (
          <p className="text-sm font-semibold text-steel">
            Pergunta {duel.question_number}/{duel.total_questions} · {DUEL_KIND[duel.kind ?? ''] ?? ''}
          </p>
        )}
      </header>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        {fighters.map((p, i) => {
          if (!p) return <span key={i} />
          const pick = duel.picks.find((k) => k.player_id === p.id)
          const card = (
            <div key={p.id} className={`flex flex-col items-center gap-1 rounded-xl bg-panel px-2 py-3 ${duel.winner === p.id ? 'mythic' : ''}`}>
              <img src={AVATAR_URLS[p.avatar]} alt="" className="size-14" />
              <span className="max-w-full truncate font-semibold">{p.id === playerId ? 'Você' : p.nickname}</span>
              {side && <span className="max-w-full truncate text-xs text-steel">{side(p.id)}</span>}
              <span className="h-5 text-sm font-semibold">
                {pick ? (pick.correct ? <span className="text-emerald-300">Acertou</span> : <span className="text-red-300">{pick.option === null ? 'Não respondeu' : 'Errou'}</span>) : duel.answered.includes(p.id) ? <span className="text-steel">Respondeu</span> : ''}
              </span>
              <span className="text-xs text-steel tabular-nums">{((duel.total_ms[p.id] ?? 0) / 1000).toFixed(1).replace('.', ',')}s no total</span>
            </div>
          )
          return i === 0 ? [card, <span key="vs" className="font-display text-3xl text-steel">vs</span>] : card
        })}
      </div>
      {body}
      {error && <p className="text-center text-red-300">{error}</p>}
    </section>
  )
}

function DuelQuestionView({
  snapshot,
  stage,
  playerId,
  remaining,
  onAnswer,
}: {
  snapshot: Snapshot
  stage: DuelStage
  playerId: string | null
  remaining: number
  onAnswer: (option: number) => Promise<void>
}) {
  const game = stage
  const duel = stage.duel
  const [choice, setChoice] = useState<number | null>(null)
  const fighting = playerId === duel.challenger || playerId === duel.rival
  const open = game.phase === 'duel_answering'
  const canAnswer = open && fighting && choice === null && !duel.answered.includes(playerId ?? '')
  const pick = async (option: number) => {
    if (!canAnswer) return
    playSound('select')
    setChoice(option)
    await onAnswer(option)
  }
  const picksOn = (index: number) => duel.picks.filter((k) => k.option === index).map((k) => snapshot.room.players.find((p) => p.id === k.player_id))
  return (
    <div className="flex flex-col gap-4">
      <div className="h-2 overflow-hidden rounded-full bg-panel">
        {open && <div className={`h-full rounded-full ${remaining < 2000 ? 'bg-red-400' : 'bg-brand'}`} style={{ width: `${Math.min(1, remaining / Math.max(1, game.phase_duration_ms)) * 100}%` }} />}
      </div>
      <h1 className="text-[1.3rem] leading-snug font-bold">{duel.text}</h1>
      <div className="grid auto-rows-fr grid-cols-2 gap-3">
        {duel.options.map((option, index) => {
          const reveal = duel.correct_option !== null
          const state = reveal
            ? index === duel.correct_option
              ? 'reveal-pop btn-correct text-white'
              : picksOn(index).length
                ? 'btn-wrong is-pressed text-white'
                : 'btn-dark opacity-40'
            : choice === index
              ? 'btn-dark is-pressed outline-2 outline-brand'
              : canAnswer
                ? 'btn-dark'
                : 'btn-dark opacity-60'
          return (
            <button
              key={index}
              onClick={() => void pick(index)}
              disabled={!canAnswer}
              className={`btn-3d btn-sm relative flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left font-semibold ${state}`}
            >
              {duel.kind !== 'true_false' && <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>}
              <span className={`min-w-0 [overflow-wrap:anywhere] ${duel.kind === 'true_false' ? 'w-full text-center text-lg' : ''}`}>{option}</span>
              {reveal && (
                <span className="absolute -top-2 -right-1.5 flex -space-x-2">
                  {picksOn(index).map((p) => p && <img key={p.id} src={AVATAR_URLS[p.avatar]} alt={p.nickname} className="size-6" />)}
                </span>
              )}
            </button>
          )
        })}
      </div>
      <p className="min-h-7 text-center font-hand text-lg font-medium text-steel">
        {open ? (fighting ? (choice === null ? 'Erre sozinho e perdeu!' : 'Resposta enviada!') : 'Torça pelo seu lado!') : ''}
      </p>
    </div>
  )
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
  useSoundsOnMount([
    ['levelHop', 450],
    ['levelUp', 1050],
  ])

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
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520], // a batida cai aos 0,15 s do som, quando o título encosta na tela
  ])
  useCountdownSounds(count)

  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">A partida vai começar</p>
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Prepare-se!</h1>
      <p className="intro-step font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        {room.settings.rounds} perguntas{game.total_rounds > room.settings.rounds && ' + a final impossível'} ·{' '}
        {room.settings.answer_seconds} segundos cada
      </p>
      <ul className="flex max-w-xs flex-wrap justify-center gap-2" aria-label="Jogadores">
        {room.players.map((player, index) => (
          <li key={player.id} className="avatar-pop" style={{ animationDelay: `${0.8 + index * 0.08}s` }}>
            <img src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-12" />
          </li>
        ))}
      </ul>
      {game.starting_powerup && (
        <p
          className={`intro-step flex items-center gap-2 rounded-xl px-4 py-2 font-semibold ${POWERUP_INFO[game.starting_powerup].tone}`}
          style={{ animationDelay: '1.2s' }}
        >
          <PowerUpIcon kind={game.starting_powerup} className="size-6" />
          Sua habilidade: {POWERUP_INFO[game.starting_powerup].name}
        </p>
      )}
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

/** Tela de preparação antes da pergunta final: chama, o carimbo "Impossível!", o placar e a contagem. */
function FinalIntro({ snapshot }: { snapshot: Snapshot }) {
  const { room } = snapshot
  const game = room.game!
  const now = useNow(true)
  const remaining = Math.max(0, snapshot.receivedAt + game.phase_ends_in_ms - now)
  const count = Math.ceil(remaining / 1000)
  const standings = [...room.players].sort((a, b) => b.score - a.score || a.answer_ms - b.answer_ms)
  useSoundsOnMount([
    ['impossible', 0],
    ['slam', 520], // a batida cai junto com o carimbo encostando na tela
  ])
  useCountdownSounds(count)

  return (
    <section className="final-intro stamp-shake relative isolate flex min-h-[72dvh] w-full flex-col items-center justify-center gap-3 overflow-hidden rounded-3xl px-4 text-center">
      <div className="final-intro-glow absolute inset-0 -z-10" aria-hidden="true" />
      <Flame />
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-orange-200 uppercase">Pergunta final</p>
      <h1 className="intro-slam stamp font-display text-6xl text-orange-300">Impossível!</h1>
      <p className="intro-step intro-step-late max-w-xs font-hand text-lg font-medium text-chalk">
        Vale 35 de QI, e errar não tira pontos. Tudo pode virar.
      </p>
      <ol className="flex max-w-xs flex-wrap justify-center gap-3" aria-label="Placar antes da final">
        {standings.map((player, index) => (
          <li key={player.id} className="avatar-pop flex flex-col items-center gap-0.5" style={{ animationDelay: `${1.1 + index * 0.08}s` }}>
            <img src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-11" />
            <span className="font-display text-sm text-orange-100 tabular-nums">{formatScore(player.score)}</span>
          </li>
        ))}
      </ol>
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

function maxBet(score: number, game: GameView) {
  return Math.max(0, Math.floor((score * game.bet_max_percent) / 100))
}

function betWin(amount: number, game: GameView) {
  return Math.floor(amount * game.bet_odds)
}

function formatOdds(odds: number) {
  return odds.toLocaleString('pt-BR')
}

/** Aposta antes da pergunta do meio das difíceis: só o tema e o nível aparecem. */
function Betting({ snapshot, playerId, onBet }: { snapshot: Snapshot; playerId: string | null; onBet: (amount: number) => Promise<string | null> }) {
  const { room, receivedAt } = snapshot
  const game = room.game!
  const me = room.players.find((p) => p.id === playerId)
  const limit = maxBet(me?.score ?? 0, game)
  const [placed, setPlaced] = useState<number | null>(null)
  const [typed, setTyped] = useState('')
  /** Atalho escolhido ('pass' ou a porcentagem); a aposta só vai ao confirmar no ✓. */
  const [shortcut, setShortcut] = useState<'pass' | number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const now = useNow(true)
  const remaining = Math.max(0, receivedAt + game.phase_ends_in_ms - now)
  const secondsLeft = Math.ceil(remaining / 1000)
  const urgent = remaining < 3000
  const done = placed !== null || (playerId !== null && game.bets_placed.includes(playerId))
  const connected = room.players.filter((p) => p.connected)
  const waitingFor = connected.filter((p) => maxBet(p.score, game) > 0)
  const betCount = waitingFor.filter((p) => game.bets_placed.includes(p.id)).length
  useSoundsOnMount([['levelUp', 0]])

  useEffect(() => {
    if (!urgent || done || limit === 0) return
    if (secondsLeft > 0) {
      vibrate(25)
      playSound('urgentTick', secondsLeft)
    }
  }, [urgent, done, limit, secondsLeft])

  const place = async (amount: number) => {
    if (done) return
    playSound('select')
    setPlaced(amount)
    setError(null)
    const failure = await onBet(amount)
    if (failure) {
      setPlaced(null)
      setError(failure)
    }
  }

  const select = (key: 'pass' | number, amount: number) => {
    playSound('select')
    setShortcut(key)
    setTyped(String(amount))
    setError(null)
  }

  const typedAmount = typed === '' ? null : Number(typed)
  const typedValid = typedAmount !== null && Number.isInteger(typedAmount) && typedAmount >= 0 && typedAmount <= limit
  const selectedClass = (key: 'pass' | number, outline: string) => (shortcut === key ? `is-pressed outline-2 ${outline}` : '')

  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">Antes da próxima pergunta</p>
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Aposta!</h1>
      <div className="intro-step flex flex-col items-center gap-2" style={{ animationDelay: '0.5s' }}>
        <span className="text-sm font-semibold text-steel">Tema da pergunta</span>
        <span className="flex flex-wrap justify-center gap-2">
          <span className="rounded-full bg-panel px-4 py-1.5 text-lg font-bold whitespace-nowrap text-chalk">{game.theme}</span>
          <span className={`rounded-full px-4 py-1.5 text-lg font-semibold whitespace-nowrap ${DIFFICULTY[game.difficulty].className}`}>
            {DIFFICULTY[game.difficulty].label}
          </span>
        </span>
      </div>

      <div className="intro-step flex w-full flex-col gap-3" style={{ animationDelay: '0.8s' }}>
        {limit === 0 ? (
          <p className="font-hand text-lg font-medium text-chalk">Sem QI para apostar. Só torce!</p>
        ) : done ? (
          <p className="font-hand text-lg font-medium text-chalk">
            {placed === 0 ? 'Você passou.' : placed !== null ? `Você apostou ${placed} de QI! Acertou, ganha ${betWin(placed, game)}; errou, perde ${placed}.` : 'Aposta feita!'}
          </p>
        ) : (
          <>
            <p className="font-hand text-lg font-medium text-chalk">
              Você tem {formatScore(me?.score ?? 0)} de QI e pode apostar até <span className="text-brand">{limit}</span>.
              Odd {formatOdds(game.bet_odds)}: acertou, ganha {Math.round((game.bet_odds - 1) * 100)}% do apostado; errou, perde tudo que apostou.
            </p>
            <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
              <button
                onClick={() => select('pass', 0)}
                className={`btn-3d btn-sm btn-dark flex flex-col items-center rounded-xl py-2 font-semibold text-steel ${selectedClass('pass', 'outline-brand')}`}
              >
                Passar
                <span className="text-xs">0</span>
              </button>
              {game.bet_percents.map((percent) => {
                const amount = Math.floor(((me?.score ?? 0) * percent) / 100)
                return (
                  <button
                    key={percent}
                    onClick={() => select(percent, amount)}
                    className={`btn-3d btn-sm flex flex-col items-center rounded-xl py-2 font-display text-lg sm:text-xl ${
                      percent === game.bet_max_percent ? 'btn-brand text-ink' : 'btn-dark text-chalk'
                    } ${selectedClass(percent, percent === game.bet_max_percent ? 'outline-chalk' : 'outline-brand')}`}
                  >
                    {percent}%
                    <span className="font-sans text-xs font-semibold opacity-80">{amount}</span>
                    <span className="font-sans text-xs font-semibold opacity-80">+{betWin(amount, game)}</span>
                  </button>
                )
              })}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (typedValid) void place(typedAmount)
              }}
              className="flex gap-2"
            >
              <input
                value={typed}
                onChange={(e) => {
                  setShortcut(null)
                  setTyped(e.target.value.replace(/\D/g, '').slice(0, 5))
                }}
                inputMode="numeric"
                placeholder={`Outro valor (0 a ${limit})`}
                aria-label="Valor da aposta"
                className="min-w-0 flex-1 rounded-xl bg-panel px-4 py-3 text-lg placeholder:text-steel focus:outline-2 focus:outline-brand"
              />
              {typedValid && (
                <button type="submit" aria-label={`Confirmar aposta de ${typedAmount}`} className="btn-3d btn-sm btn-brand rounded-xl px-5 font-display text-2xl text-ink">
                  ✓
                </button>
              )}
            </form>
          </>
        )}
        {error && <p className="text-red-300">{error}</p>}
      </div>

      <div className="flex w-full items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel">
          <div
            className={`h-full rounded-full ${urgent ? 'bg-red-400' : 'bg-amber-200'}`}
            style={{ width: `${Math.min(1, remaining / Math.max(1, game.phase_duration_ms)) * 100}%` }}
          />
        </div>
        <span key={urgent ? secondsLeft : 'calm'} className={`w-8 text-right font-display text-2xl tabular-nums ${urgent ? 'timer-urgent text-red-400' : ''}`}>
          {secondsLeft}
        </span>
      </div>
      <p className="font-hand text-lg font-medium text-steel">
        {betCount}/{waitingFor.length} já apostaram
      </p>
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

function formatScore(score: number) {
  return score < 0 ? `−${-score}` : `${score}`
}

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
  onArm: Props['onArm']
  onUse: Props['onUse']
  onSkip: Props['onSkip']
}

function Round({ snapshot, game, playerId, onAnswer, onArm, onUse, onSkip }: RoundProps) {
  const { room, receivedAt } = snapshot
  const [choice, setChoice] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const timed = game.phase !== 'finished'
  const now = useNow(timed)
  const remaining = Math.max(0, receivedAt + game.phase_ends_in_ms - now)
  const progress = game.phase_duration_ms > 0 ? 1 - remaining / game.phase_duration_ms : 1

  // Na resposta, a barra fica cheia e dourada durante a carência (pontos máximos)
  // e depois esvazia até o fim do tempo, junto com os pontos.
  const graceMs = game.speed_grace_ms
  const inGrace = game.phase === 'answering' && game.phase_duration_ms - remaining < graceMs
  const barFill =
    game.phase === 'answering'
      ? inGrace
        ? 1
        : remaining / Math.max(1, game.phase_duration_ms - graceMs)
      : 1 - progress

  const question = game.question!
  const typing = game.phase === 'reading'
  const hits = (kind: PowerUpUse['kind']) =>
    game.phase !== 'results' && game.active.some((use) => use.kind === kind && (use.legendary ? use.by !== playerId : use.target === playerId))
  const silenced = game.silenced_rounds > 0
  const scrambled = hits('scramble')
  const fullText = scrambled ? scrambleWords(question.text, game.round) : question.text
  const text = typing ? fullText.slice(0, Math.ceil(fullText.length * progress)) : fullText
  const mirrored = hits('mirror') ? '-scale-x-100' : ''
  // Segunda chance: a primeira escolha errada não encerra a sua resposta.
  const retry = game.first_wrong
  const answered = retry !== null ? choice !== null && choice !== retry : choice !== null || (playerId !== null && game.answered.includes(playerId))
  const canAnswer = game.phase === 'answering' && !answered
  const showResults = game.phase === 'results' && !silenced
  const hiddenReveal = game.phase === 'results' && silenced
  const myResult = game.results.find((r) => r.player_id === playerId)
  const connectedCount = room.players.filter((p) => p.connected).length
  const difficulty = DIFFICULTY[question.difficulty]
  const secondsLeft = Math.ceil(remaining / 1000)
  const urgent = game.phase === 'answering' && remaining < 3000 && !silenced
  const blinded = game.flashbang && game.phase === 'answering' && game.phase_duration_ms - remaining >= FLASHBANG_MS
  const scratched = hits('scratch') && !blinded

  useEffect(() => {
    if (typing && text.length > 0 && text.length % 3 === 0) playSound('typing')
  }, [typing, text.length])

  useEffect(() => {
    if (game.phase === 'answering') playSound('answersOpen')
  }, [game.phase])

  // Uma sabotagem em você toca o "ops" quando a pergunta abre (o Roubo é surpresa: não toca).
  const sabotaged = game.active.some((use) => use.kind !== 'steal' && TARGETED_KINDS.has(use.kind) && (use.legendary ? use.by !== playerId : use.target === playerId))
  useEffect(() => {
    if (sabotaged && !showResults) playSound('powerHit')
    // Só quando a pergunta aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])

  // Vibra e faz tique-taque a cada um dos 3 últimos segundos, só para quem ainda não respondeu.
  useEffect(() => {
    if (!urgent || answered) return
    if (secondsLeft > 0) {
      vibrate(25)
      playSound('urgentTick', secondsLeft)
    } else {
      playSound('timeUp')
    }
  }, [urgent, answered, secondsLeft])

  // Depende só do veredito: cada atualização da sala (Pular, habilidade armada) recria o resultado.
  const verdict = showResults && myResult ? (myResult.option === null ? 'noAnswer' : myResult.correct ? 'correct' : 'wrong') : null
  useEffect(() => {
    if (!verdict) return
    if (verdict !== 'noAnswer') vibrate(verdict === 'correct' ? 40 : [70, 50, 70])
    playSound(verdict)
  }, [verdict])

  const pick = async (option: number) => {
    if (!canAnswer || game.hidden_options.includes(option) || option === retry) return
    playSound('select')
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
      return 'btn-dark [&>span:not(.voters)]:opacity-40'
    }
    if (index === retry) return 'btn-wrong is-pressed text-white opacity-60'
    if (chosen) return 'btn-dark is-pressed outline-2 outline-brand'
    if (game.hidden_options.includes(index)) return 'btn-dark opacity-20 line-through'
    if (!canAnswer) return 'btn-dark opacity-50'
    return 'btn-dark'
  }

  return (
    <section className="flex w-full flex-col gap-5">
      <header className="flex items-center justify-between gap-2 text-sm">
        <span className="flex shrink-0 items-center gap-2 font-semibold whitespace-nowrap text-steel">
          {game.round > room.settings.rounds ? 'Pergunta extra' : `Pergunta ${game.round}/${room.settings.rounds}`}
          <StreakChip streak={room.players.find((p) => p.id === playerId)?.streak ?? 0} />
        </span>
        {/* Uma linha só: tema longo corta com reticências, o selo de dificuldade nunca encolhe. */}
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0 truncate rounded-full bg-panel px-2.5 py-1 text-steel" title={question.theme}>
            {question.theme}
          </span>
          <span className={`round-chip shrink-0 rounded-full px-2.5 py-1 font-semibold whitespace-nowrap ${difficulty.className}`}>{difficulty.label}</span>
        </span>
      </header>

      {blinded && <div className="flashbang-flash" aria-hidden="true" />}
      {!silenced && <ResurrectionOverlay revivals={game.revivals} players={room.players} playerId={playerId} />}
      {/* Na Flashbang o aviso fica invisível sem sair do lugar: tirar da página deixava um rastro do contorno. */}
      {!showResults && <ActivePowerUps game={game} players={room.players} playerId={playerId} concealed={blinded} />}
      {!showResults && !answered && !silenced && <InstantPowerUps game={game} playerId={playerId} onUse={onUse} />}

      <div className={`flex h-8 items-center gap-3 ${silenced ? 'invisible' : ''}`}>
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

      <Magnifier active={hits('magnifier') && !blinded}>
        {/* Altura reservada para até 3 linhas: o texto digitando não empurra as alternativas. */}
        <ScratchCard active={scratched}>
          <h1 className={`round-question min-h-[6.25rem] text-[1.4rem] leading-snug font-bold ${mirrored}`}>
            {blinded ? '' : text}
            {typing && <span className="ml-0.5 inline-block w-[0.5ch] animate-pulse text-brand">|</span>}
          </h1>
        </ScratchCard>

        <div className="grid auto-rows-fr grid-cols-2 gap-3">
          {question.options.map((option, index) => (
            <ScratchCard key={index} active={scratched && !game.hidden_options.includes(index)} className="flex">
              <button
                onClick={() => pick(index)}
                disabled={!canAnswer || game.hidden_options.includes(index) || index === retry}
                style={{ animationDelay: `${0.12 + index * 0.06}s` }}
                className={`round-option btn-3d btn-sm relative flex min-h-14 w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${optionClass(index)}`}
              >
                <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
                <span className={`min-w-0 [overflow-wrap:anywhere] ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(option, game.round * 7 + index + 1) : option}</span>
                {game.peek && !showResults && <PeekBadge count={game.peek[index]} />}
                {game.tolls && !showResults && <TollBadge price={game.tolls[index]} />}
                {showResults && <Voters players={room.players.filter((p) => game.results.some((r) => r.player_id === p.id && r.option === index))} />}
              </button>
            </ScratchCard>
          ))}
        </div>
      </Magnifier>

      {error && <p className="text-center text-red-300">{error}</p>}

      {showResults ? (
        <RoundSummary room={room} game={game} playerId={playerId} onArm={onArm} onSkip={onSkip} />
      ) : hiddenReveal ? (
        <SilencedReveal roundsLeft={game.silenced_rounds} />
      ) : (
        <p className="min-h-7 text-center font-hand font-medium text-lg text-steel">
          {typing
            ? 'Leia com atenção…'
            : blinded && !answered
              ? 'Flashbang! Agora é chutar pela letra.'
              : retry !== null && !answered
              ? 'Errou! Segunda chance: tente de novo (vale metade).'
              : silenced
                ? answered
                  ? 'Resposta enviada! Agora é esperar…'
                  : 'Silêncio… quanto tempo será que falta?'
                : answered
                  ? `Resposta enviada! Esperando a galera (${game.answered.length}/${connectedCount})`
                  : `${game.answered.length}/${connectedCount} já responderam`}
        </p>
      )}
    </section>
  )
}

const RESURRECTION_MS = 3600
const SPARKS = [8, 22, 35, 50, 63, 77, 90].map((left, i) => ({ left, delay: 0.3 + (i % 4) * 0.35, size: 4 + (i % 3) * 2 }))

/** Ressurreição: luz descendo do céu, o avatar subindo com auréola e asas, e o coral. Uma vez por uso. */
function ResurrectionOverlay({ revivals, players, playerId }: { revivals: GameView['revivals']; players: PlayerView[]; playerId: string | null }) {
  const [done, setDone] = useState<Set<string>>(() => new Set())
  const key = (r: GameView['revivals'][number]) => `${r.player_id}:${r.after}`
  const current = revivals.find((r) => !done.has(key(r))) ?? null
  const currentKey = current ? key(current) : null

  useEffect(() => {
    if (!currentKey) return
    playSound('resurrection')
    const sparkle = setTimeout(() => playSound('perfectEasy'), 1100)
    const finish = setTimeout(() => setDone((s) => new Set(s).add(currentKey)), RESURRECTION_MS)
    return () => {
      clearTimeout(sparkle)
      clearTimeout(finish)
    }
  }, [currentKey])

  if (!current) return null
  const player = players.find((p) => p.id === current.player_id)
  const me = current.player_id === playerId
  return (
    <div className="res-overlay" role="status" aria-label="Ressurreição">
      <div className="res-rays" aria-hidden="true" />
      {SPARKS.map((s, i) => (
        <span key={i} className="res-spark" style={{ left: `${s.left}%`, width: s.size, height: s.size, animationDelay: `${s.delay}s` }} aria-hidden="true" />
      ))}
      <div className="res-rise relative flex flex-col items-center">
        <span className="res-halo" aria-hidden="true" />
        <div className="relative flex items-center">
          <Wing className="res-wing res-wing-left" />
          {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="res-avatar relative size-28" />}
          <Wing className="res-wing res-wing-right" />
        </div>
      </div>
      <p className="res-title font-display text-6xl text-amber-100 [text-shadow:0_0_24px_rgba(255,214,102,0.9)]">Ressurreição!</p>
      <p className="res-sub max-w-xs text-center text-lg font-semibold text-amber-50">
        {me ? 'Você voltou dos mortos' : `${player?.nickname ?? 'Alguém'} voltou dos mortos`}: {formatScore(current.before)} → {formatScore(current.after)} de QI
      </p>
    </div>
  )
}

function Wing({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 60 48" className={className} aria-hidden="true">
      <path
        d="M58 30C46 12 30 3 4 2c8 6 12 10 14 14-6-1-11-1-16 1 8 3 13 6 16 10-5 0-9 1-13 4 9 2 16 5 22 9 12 6 24 3 31-10Z"
        fill="#FFFBEB"
        stroke="#F2C14E"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M50 30C40 22 30 17 18 16M46 34c-9-4-18-6-28-6" fill="none" stroke="#F2C14E" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

/** No lugar da revelação, para quem está silenciado: sem resposta certa, sem placar e sem habilidades. */
function SilencedReveal({ roundsLeft }: { roundsLeft: number }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl bg-panel px-4 py-5 text-center">
      <PowerUpIcon kind="silence" className="size-10" />
      <p className="font-display text-3xl tracking-wide text-chalk">Silenciado!</p>
      <p className="text-steel">Nada de resposta, placar ou habilidades por enquanto.</p>
      <p className="font-hand text-lg font-medium text-steel">{roundsLeft > 1 ? 'Ainda falta mais uma pergunta em silêncio.' : 'Na próxima você volta a ver tudo.'}</p>
    </div>
  )
}

interface SummaryProps {
  room: RoomState
  game: GameView
  playerId: string | null
  onArm: Props['onArm']
  onSkip: Props['onSkip']
}

function RoundSummary({ room, game, playerId, onArm, onSkip }: SummaryProps) {
  const mine = game.results.find((r) => r.player_id === playerId)
  const deltas: Record<string, number> = Object.fromEntries(
    game.results.map((r) => [r.player_id, r.delta + bonusTotal(r) + r.bet_delta + r.stolen - r.robbed + r.toll_received - r.tolled + r.tricked]),
  )
  for (const revival of game.revivals) deltas[revival.player_id] = (deltas[revival.player_id] ?? 0) + revival.after - revival.before
  const bets = game.results.filter((r) => r.bet)
  const highlights = game.results.flatMap((r) => r.bonuses.map((bonus) => ({ result: r, bonus })))
  const powerupLines = powerupEvents(room, game, playerId)

  // O "trrr" acompanha o seu QI contando; cada tipo de bônus da rodada toca uma vez, junto com a faixa.
  const bonusSounds: Record<Bonus['kind'], SoundId> = { streak: 'streakFire', wrong_streak: 'streakIce', perfect_easy: 'perfectEasy', investment: 'investment' }
  const kinds = [...new Set(highlights.map((h) => h.bonus.kind))]
  useSoundsOnMount([
    ...kinds.map((kind): [SoundId, number] => [bonusSounds[kind], 400 + highlights.findIndex((h) => h.bonus.kind === kind) * 120]),
    ...(mine?.shielded ? [['shield', 250] as [SoundId, number]] : []),
  ])
  useEffect(() => {
    if (mine && mine.delta !== 0) playSound('countUp', mine.delta)
    // Só quando o resumo aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      <PowerUpBar powers={room.settings.mode === 'powers'} game={game} players={room.players} playerId={playerId} onArm={onArm} onSkip={onSkip} />
      {powerupLines.length > 0 && (
        <ul className="flex flex-col gap-1.5" aria-label="Habilidades">
          {powerupLines.map(({ key, kind, player, text, delta, me, legendary, mythic }, index) => (
            <li
              key={key}
              className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold ${legendary ? 'legendary' : mythic ? 'mythic' : POWERUP_INFO[kind].tone} ${me && !legendary && !mythic ? 'ring-1 ring-brand/60' : ''}`}
              style={{ animationDelay: `${0.4 + index * 0.12}s` }}
            >
              {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />}
              <PowerUpIcon kind={kind} className="size-5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{text}</span>
              {delta !== null && <span className="font-display text-lg">{formatDelta(delta)}</span>}
            </li>
          ))}
        </ul>
      )}
      {bets.length > 0 && (
        <ul className="flex flex-col gap-1.5" aria-label="Apostas">
          {bets.map((result, index) => {
            const player = room.players.find((p) => p.id === result.player_id)
            return (
              <li
                key={result.player_id}
                className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold ${
                  result.bet_delta > 0 ? 'bg-emerald-500/15 text-emerald-200' : 'bg-red-500/15 text-red-200'
                } ${result.player_id === playerId ? 'ring-1 ring-brand/60' : ''}`}
                style={{ animationDelay: `${0.4 + index * 0.12}s` }}
              >
                {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />}
                <span className="min-w-0 flex-1 truncate">
                  {result.player_id === playerId ? 'Você' : player?.nickname} apostou {result.bet}
                  {result.bet === maxBet(player ? player.score - deltas[result.player_id] : 0, game) && ' (tudo que podia!)'}
                </span>
                <span className="font-display text-lg">{formatDelta(result.bet_delta)}</span>
              </li>
            )
          })}
        </ul>
      )}
      {highlights.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {highlights.map(({ result, bonus }, index) => {
            const player = room.players.find((p) => p.id === result.player_id)
            return (
              <li
                key={`${result.player_id}-${bonus.kind}-${bonus.count}`}
                className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold ${BONUS_STYLE[bonus.kind]} ${
                  result.player_id === playerId ? 'ring-1 ring-brand/60' : ''
                }`}
                style={{ animationDelay: `${0.4 + index * 0.12}s` }}
              >
                {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />}
                <BonusIcon kind={bonus.kind} className="size-5 shrink-0" />
                <span className="min-w-0 flex-1 truncate">
                  {result.player_id === playerId ? 'Você' : player?.nickname}: {bonusLabel(bonus)}
                </span>
                <span className="font-display text-lg">{formatDelta(bonus.delta)}</span>
              </li>
            )
          })}
        </ul>
      )}
      {game.fact && (
        <div className="rounded-xl border border-brand/30 bg-brand/10 px-4 py-3">
          <p className="flex items-center gap-1.5 font-display text-lg tracking-wide text-brand">
            <BulbIcon className="size-5" />
            Você sabia?
          </p>
          <p className="mt-1 leading-relaxed">{game.fact}</p>
        </div>
      )}
      <Ranking
        players={room.players}
        playerId={playerId}
        deltas={deltas}
        picks={Object.fromEntries(game.results.map((r) => [r.player_id, r]))}
      />
    </div>
  )
}

/** Linhas da revelação: escudos que seguraram, roubos e habilidades ganhas. */
function powerupEvents(room: RoomState, game: GameView, playerId: string | null) {
  const who = (id: string | null) => (id === playerId ? 'Você' : (room.players.find((p) => p.id === id)?.nickname ?? '?'))
  const lines: { key: string; kind: PowerUpUse['kind']; player?: PlayerView; text: string; delta: number | null; me: boolean; legendary?: boolean; mythic?: boolean }[] = []
  const mine = game.results.find((r) => r.player_id === playerId)
  for (const result of game.results) {
    const player = room.players.find((p) => p.id === result.player_id)
    const me = result.player_id === playerId
    for (const kind of result.expired) {
      lines.push({ key: `${result.player_id}-${kind}-expired`, kind, player, text: `${who(result.player_id)}: ${POWERUP_INFO[kind].name} quebrou sem ser usado.`, delta: null, me })
    }
    if (result.doubled) {
      lines.push({ key: `${result.player_id}-double`, kind: 'double', player, text: `${who(result.player_id)}: Dobro!`, delta: result.delta, me })
    }
    if (result.first_option !== null) {
      const text = result.correct ? 'acertou na segunda chance (metade)!' : 'errou de novo na segunda chance.'
      lines.push({ key: `${result.player_id}-second`, kind: 'second_chance', player, text: `${who(result.player_id)} ${text}`, delta: null, me })
    }
    if (result.shielded) {
      lines.push({ key: `${result.player_id}-shield`, kind: 'shield', player, text: `${who(result.player_id)}: o Escudo segurou ${result.shielded} de QI!`, delta: null, me })
    }
    const steal = game.active.find((use) => use.kind === 'steal' && use.by === result.player_id)
    if (steal?.legendary) {
      lines.push({
        key: `${result.player_id}-steal`,
        kind: 'steal',
        player,
        text: result.stolen ? `${who(result.player_id)} roubou de todo mundo com o Roubo lendário!` : `${who(result.player_id)} não roubou nada com o Roubo lendário.`,
        delta: result.stolen ? (me ? result.stolen : -(mine?.robbed ?? 0)) : null, // do ponto de vista de quem lê
        me: true,
        legendary: true,
      })
    } else if (steal) {
      const target = who(steal.target)
      if (steal.reflected_by) {
        lines.push({
          key: `${result.player_id}-reverse`,
          kind: 'reverse',
          player,
          text: `${who(result.player_id)} rebateu o Roubo de ${target === 'Você' ? 'você' : target} com o Reverso!`,
          delta: null,
          me: me || steal.target === playerId,
        })
      }
      lines.push({
        key: `${result.player_id}-steal`,
        kind: 'steal',
        player,
        text: result.stolen ? `${who(result.player_id)} roubou de ${target === 'Você' ? 'você' : target}!` : `${who(result.player_id)} não roubou nada de ${target === 'Você' ? 'você' : target}.`,
        delta: result.stolen ? (steal.target === playerId ? -result.stolen : result.stolen) : null, // do ponto de vista de quem lê
        me: me || steal.target === playerId,
      })
    }
    if (result.decoy) {
      lines.push({ key: `${result.player_id}-decoy`, kind: 'decoy', player, text: `${who(result.player_id)} caiu na Alternativa falsa: "${result.decoy}"!`, delta: null, me })
    }
    if (result.tricked) {
      lines.push({ key: `${result.player_id}-tricked`, kind: 'decoy', player, text: `${who(result.player_id)} ganhou ${result.tricked} com a Alternativa falsa!`, delta: me ? result.tricked : null, me })
    }
    if (result.tolled) {
      lines.push({ key: `${result.player_id}-tolled`, kind: 'toll', player, text: `${who(result.player_id)} pagou ${result.tolled} de Pedágio.`, delta: me ? -result.tolled : null, me })
    }
    if (result.toll_received) {
      lines.push({ key: `${result.player_id}-toll`, kind: 'toll', player, text: `${who(result.player_id)} recebeu ${result.toll_received} de Pedágio!`, delta: me ? result.toll_received : null, me })
    }
    if (result.gained) {
      lines.push({ key: `${result.player_id}-gain`, kind: result.gained.kind, player, text: `${who(result.player_id)} ${gainLabel(result.gained)}`, delta: null, me, legendary: result.gained.legendary, mythic: result.gained.mythic })
    }
  }
  for (const { challenger, rival } of game.duels) {
    lines.push({
      key: `${challenger}-${rival}-duel`,
      kind: 'duel',
      player: room.players.find((p) => p.id === challenger),
      text: `${who(challenger)} chamou ${rival === playerId ? 'você' : who(rival)} pro X1! Começa quando a revelação acabar.`,
      delta: null,
      me: challenger === playerId || rival === playerId,
      mythic: true,
    })
  }
  for (const revival of game.revivals) {
    const me = revival.player_id === playerId
    lines.push({
      key: `${revival.player_id}-revival`,
      kind: 'resurrection',
      player: room.players.find((p) => p.id === revival.player_id),
      text: `${who(revival.player_id)} usou a Ressurreição: de ${formatScore(revival.before)} para ${formatScore(revival.after)} de QI!`,
      delta: me ? revival.after - revival.before : null,
      me,
      mythic: true,
    })
  }
  return lines
}

const BONUS_STYLE: Record<Bonus['kind'], string> = {
  perfect_easy: 'bg-brand/15 text-brand',
  streak: 'bg-orange-500/15 text-orange-200',
  wrong_streak: 'bg-sky-400/10 text-sky-200',
  investment: 'bg-green-500/15 text-green-200',
}

function bonusLabel(bonus: Bonus) {
  if (bonus.kind === 'perfect_easy') return 'gabaritou as fáceis!'
  if (bonus.kind === 'investment') return bonus.count === 5 ? 'Investimento completo!' : `Investimento, ${bonus.count}º acerto!`
  const again = bonus.repeat ? ' de novo' : ''
  if (bonus.kind === 'streak') return `${bonus.count} acertos seguidos${again}!`
  return `${bonus.count} erros seguidos${again}!`
}

function bonusTotal(result: RoundResult) {
  return result.bonuses.reduce((sum, bonus) => sum + bonus.delta, 0)
}

function BonusIcon({ kind, className }: { kind: Bonus['kind']; className?: string }) {
  if (kind === 'perfect_easy') return <StarIcon className={className} />
  if (kind === 'streak') return <FlameIcon className={className} />
  if (kind === 'investment') return <PowerUpIcon kind="investment" className={className} />
  return <SnowflakeIcon className={className} />
}

/** Sequência atual no cabeçalho: foguinho a partir de 2 acertos seguidos, gelo a partir de 2 erros. */
function StreakChip({ streak }: { streak: number }) {
  if (Math.abs(streak) < 2) return null
  const hot = streak > 0
  return (
    <span
      className={`round-chip flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${
        hot ? 'bg-orange-500/20 text-orange-300' : 'bg-sky-400/15 text-sky-200'
      }`}
      title={hot ? `${streak} acertos seguidos` : `${-streak} erros seguidos`}
    >
      {hot ? <FlameIcon className="size-3.5" /> : <SnowflakeIcon className="size-3.5" />}
      {Math.abs(streak)}
    </span>
  )
}

export function PeekBadge({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <span className="absolute -top-2 -right-1.5 flex items-center gap-0.5 rounded-full bg-teal-300 px-1.5 text-xs font-bold text-ink" title={`${count} escolheram`}>
      <PowerUpIcon kind="peek" className="size-3.5" />
      {count}
    </span>
  )
}

function TollBadge({ price }: { price: number }) {
  return (
    <span className="absolute -bottom-2 -right-1.5 flex items-center gap-0.5 rounded-full bg-rose-300 px-1.5 text-xs font-bold text-ink" title={`Responder esta custa ${price} de QI`}>
      <PowerUpIcon kind="toll" className="size-3.5" />−{price}
    </span>
  )
}

const MAX_VOTERS = 4
const TARGETED_KINDS = new Set(Object.entries(POWERUP_INFO).filter(([, info]) => info.targeted).map(([kind]) => kind))
const FLASHBANG_MS = 4000

function Voters({ players }: { players: PlayerView[] }) {
  if (players.length === 0) return null
  const shown = players.slice(0, players.length > MAX_VOTERS ? MAX_VOTERS - 1 : MAX_VOTERS)
  const hidden = players.length - shown.length
  return (
    <span className="voters absolute -bottom-3 right-1.5 flex" title={players.map((p) => p.nickname).join(', ')}>
      {shown.map((player, index) => (
        <img
          key={player.id}
          src={AVATAR_URLS[player.avatar]}
          alt={player.nickname}
          className="avatar-pop -ml-2.5 size-7 rounded-full border-2 border-ink first:ml-0"
          style={{ animationDelay: `${0.5 + index * 0.08}s` }}
        />
      ))}
      {hidden > 0 && (
        <span
          className="avatar-pop -ml-2.5 flex size-7 items-center justify-center rounded-full border-2 border-ink bg-chalk text-xs font-bold text-ink"
          style={{ animationDelay: `${0.5 + shown.length * 0.08}s` }}
        >
          +{hidden}
        </span>
      )}
    </span>
  )
}

function PickBadge({ result }: { result: RoundResult }) {
  const tone = result.option === null ? 'bg-[#232b3f] text-steel' : result.correct ? 'bg-emerald-600 text-white' : 'bg-red-500 text-white'
  return (
    <span className={`flex size-7 shrink-0 items-center justify-center rounded-lg font-display text-base ${tone}`}>
      {result.option === null ? '—' : LETTERS[result.option]}
    </span>
  )
}

interface RankingProps {
  players: PlayerView[]
  playerId: string | null
  deltas?: Record<string, number>
  picks?: Record<string, RoundResult>
}

function Ranking({ players, playerId, deltas, picks }: RankingProps) {
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
    if (items.some((el, index) => before.indexOf(el.dataset.id!) !== index)) setTimeout(() => playSound('rankingSwish'), 350)
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
          <span className="min-w-0 truncate font-semibold">{player.nickname}</span>
          {picks?.[player.id] && <PickBadge result={picks[player.id]} />}
          <span className="flex-1" />
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

// Momentos da revelação do pódio, em ms: 3º, 2º, 1º (com fanfarra e confete), o último e, por fim, o resto da tela.
const PODIUM_STEPS = [900, 2300, 3800, 6300, 8000]

const PODIUM_PLACES = [
  { place: 1, label: '1º', step: 'h-24 bg-brand text-ink', order: 'order-2' },
  { place: 2, label: '2º', step: 'h-16 bg-slate-300 text-ink', order: 'order-1' },
  { place: 3, label: '3º', step: 'h-10 bg-amber-700 text-chalk', order: 'order-3' },
]

/** Fim de jogo em etapas: o pódio enche do 3º para o 1º, depois aparece quem sabe menos. */
function Podium({ room, playerId, onPlayAgain, onLeave }: PodiumProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const sorted = [...room.players].sort(byRanking)
  const worst = sorted.length > 1 ? sorted[sorted.length - 1] : null
  const isHost = room.host_id === playerId
  const places = PODIUM_PLACES.filter((p) => p.place <= sorted.length)

  // Quantas etapas já foram reveladas (0 = pódio vazio; PODIUM_STEPS.length = tudo).
  const [stage, setStage] = useState(() => (reducedMotion() ? PODIUM_STEPS.length : 0))
  useEffect(() => {
    if (stage >= PODIUM_STEPS.length) return
    const timers = PODIUM_STEPS.map((ms, i) => setTimeout(() => setStage((s) => Math.max(s, i + 1)), ms))
    return () => timers.forEach(clearTimeout)
    // Agenda uma vez, quando o pódio aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const revealed = (place: number) => stage >= 4 - place
  useEffect(() => {
    const sounds: Record<number, SoundId | undefined> = { 1: 'slam', 2: 'slam', 3: 'podiumWinner', 4: worst ? 'podiumLoser' : undefined }
    const sound = sounds[stage]
    if (sound && !(stage === 1 && sorted.length < 3)) playSound(sound)
    // Só quando a etapa muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage])

  const done = stage >= PODIUM_STEPS.length

  return (
    <section className="flex w-full flex-col gap-6">
      <h1 className="text-center font-display text-5xl tracking-wide text-brand">Fim de jogo!</h1>

      <div className="relative flex items-end justify-center gap-2" aria-label="Pódio">
        {stage >= 3 && <Confetti />}
        {places.map(({ place, label, step, order }) => {
          const player = sorted[place - 1]
          const shown = revealed(place)
          return (
            <div key={place} className={`flex w-1/3 max-w-36 flex-col items-center gap-1.5 ${order}`}>
              <div className="relative flex min-h-36 w-full flex-col items-center justify-end gap-1 text-center">
                {shown ? (
                  <div key="shown" className="podium-card relative flex w-full flex-col items-center gap-1">
                    <div className="relative">
                      <img src={AVATAR_URLS[player.avatar]} alt="" className={place === 1 ? 'size-20' : 'size-16'} />
                      {place === 1 && <img src={coroa} alt="" className="icon-bounce absolute -top-5 -right-5 size-10" />}
                    </div>
                    <span className="w-full truncate font-bold">{player.nickname}</span>
                    <span className="font-display text-xl text-brand">{formatScore(player.score)} QI</span>
                  </div>
                ) : (
                  <span className="font-display text-5xl text-steel/40">?</span>
                )}
              </div>
              <div className={`flex w-full items-start justify-center rounded-t-xl pt-1 font-display text-2xl ${step}`}>{label}</div>
            </div>
          )
        })}
      </div>

      {worst && stage >= 4 && <Highlight title="Quem sabe menos" icon={haha} player={worst} tone="text-red-300" />}

      {done ? (
        <>
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
        </>
      ) : (
        <button onClick={() => setStage(PODIUM_STEPS.length)} className="mx-auto font-semibold text-steel underline-offset-4 hover:underline">
          Pular
        </button>
      )}
    </section>
  )
}

const CONFETTI_COLORS = ['#FFC107', '#F8FAFC', '#34D399', '#F87171', '#60A5FA', '#FB923C']

/** Confete caindo sobre o cartão do vencedor. Posições fixas por índice (sem aleatório a cada render). */
export function Confetti() {
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
