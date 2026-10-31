import { useEffect, useState } from 'react'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount } from '../lib/effects'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { EstimateGuess, EstimateView, PlayerView } from '../types/events'
import { formatDelta } from '../lib/format'
import { DifficultyChip, FactCard, LevelIntro, Podium, Ranking } from './Game'
import { LeaveButton } from './LeaveButton'

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onGuess: (value: number) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Chutômetro: a resposta é um número; quanto mais perto, mais QI. */
export function Estimate({ snapshot, playerId, onGuess, onSkip, onPlayAgain, onLeave }: Props) {
  const estimate = snapshot.room.estimate!
  if (estimate.phase === 'finished') {
    return <Podium room={snapshot.room} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  }
  if (estimate.phase === 'starting') {
    return <EstimateStart snapshot={snapshot} />
  }
  if (estimate.phase === 'level') {
    return <LevelIntro difficulty={estimate.difficulty} />
  }
  // key: cada pergunta começa com o campo vazio.
  return <EstimateRound key={estimate.round} snapshot={snapshot} playerId={playerId} onGuess={onGuess} onSkip={onSkip} onLeave={onLeave} />
}

/** "1.500", "1500", "3,14" e "-89,2" viram número; o resto é inválido. */
function parseGuess(raw: string): number | null {
  let text = raw.trim().replace(/\s/g, '').replace('−', '-')
  if (!/^-?[\d.,]+$/.test(text)) return null
  if (text.includes(',')) {
    text = text.replace(/\./g, '').replace(',', '.')
  } else if (/^-?\d{1,3}(\.\d{3})+$/.test(text)) {
    text = text.replace(/\./g, '') // ponto de milhar, como em 1.500
  }
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/** Anos e números sem unidade ficam sem ponto de milhar ("1822", não "1.822"). */
function formatNumber(value: number, unit: string | null | undefined) {
  const grouped = !!unit && unit !== 'a.C.'
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3, useGrouping: grouped }).format(value)
}

function withUnit(value: number, unit: string | null | undefined) {
  return unit ? `${formatNumber(value, unit)} ${unit}` : formatNumber(value, unit)
}

function EstimateStart({ snapshot }: { snapshot: Snapshot }) {
  const estimate = snapshot.room.estimate!
  const now = useNow(true)
  const count = Math.ceil(Math.max(0, snapshot.receivedAt + estimate.phase_ends_in_ms - now) / 1000)
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520],
  ])
  useCountdownSounds(count)

  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">Chutômetro</p>
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Prepare-se!</h1>
      <p className="intro-step max-w-xs font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        {estimate.total_rounds} perguntas de número. Chegou perto, ganha QI; chutou pra lua, perde.
      </p>
      <ul className="flex max-w-xs flex-wrap justify-center gap-2" aria-label="Jogadores">
        {snapshot.room.players.map((player, index) => (
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

interface RoundProps {
  snapshot: Snapshot
  playerId: string | null
  onGuess: Props['onGuess']
  onSkip: Props['onSkip']
  onLeave: Props['onLeave']
}

function EstimateRound({ snapshot, playerId, onGuess, onSkip, onLeave }: RoundProps) {
  const { room, receivedAt } = snapshot
  const estimate = room.estimate!
  const now = useNow(estimate.phase === 'answering' || estimate.phase === 'results')
  const [draft, setDraft] = useState('')
  const [negative, setNegative] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const remaining = Math.max(0, receivedAt + estimate.phase_ends_in_ms - now)
  const answering = estimate.phase === 'answering'
  const results = estimate.phase === 'results'
  const guessed = estimate.my_guess !== null && estimate.my_guess !== undefined
  const mine = estimate.guesses.find((g) => g.player_id === playerId)

  useEffect(() => {
    if (answering) playSound('answersOpen')
  }, [answering])
  useEffect(() => {
    if (!results || !mine) return
    playSound(mine.value === null ? 'noAnswer' : mine.delta > 0 ? 'correct' : 'wrong')
    // Só quando a revelação aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results])

  const submit = async () => {
    const parsed = parseGuess(draft)
    if (parsed === null) {
      setError('Digite só o número, como 1500 ou 3,14.')
      return
    }
    playSound('select')
    setError(await onGuess(negative ? -Math.abs(parsed) : parsed))
  }

  return (
    <section className="flex w-full flex-col gap-5">
      <header className="flex items-center justify-between gap-2 text-sm">
        <span className="font-semibold whitespace-nowrap text-steel">
          Pergunta {estimate.round}/{estimate.total_rounds}
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0 truncate rounded-full bg-panel px-2.5 py-1 text-steel">{estimate.theme}</span>
          <DifficultyChip difficulty={estimate.difficulty} />
        </span>
      </header>

      {/* Na resposta, o tempo para chutar; na revelação, quanto falta para a próxima pergunta. */}
      <div className="h-2 overflow-hidden rounded-full bg-panel">
        {(answering || results) && (
          <div
            className={`h-full rounded-full ${results ? 'bg-steel/60' : remaining < 5000 ? 'bg-red-400' : 'bg-amber-200'}`}
            style={{ width: `${Math.min(1, remaining / Math.max(1, estimate.phase_duration_ms)) * 100}%` }}
          />
        )}
      </div>

      <h2 className="text-center font-display text-3xl leading-tight tracking-wide">{estimate.text}</h2>

      {results ? (
        <Reveal estimate={estimate} players={room.players} playerId={playerId} onSkip={onSkip} />
      ) : guessed ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-steel">Seu chute</p>
          <p className="font-display text-5xl text-brand">{withUnit(estimate.my_guess!, estimate.unit)}</p>
          <Waiting players={room.players} answered={estimate.answered} />
        </div>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <div className="flex items-stretch gap-2">
            <button
              type="button"
              onClick={() => setNegative((n) => !n)}
              disabled={!answering}
              aria-pressed={negative}
              aria-label="Número negativo"
              className={`btn-3d btn-sm w-12 shrink-0 rounded-xl font-display text-2xl ${negative ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel'}`}
            >
              −
            </button>
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl bg-panel px-4 focus-within:outline-2 focus-within:outline-brand">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                inputMode="decimal"
                autoComplete="off"
                enterKeyHint="send"
                placeholder="Seu chute"
                disabled={!answering}
                aria-label="Seu chute"
                className="min-w-0 flex-1 bg-transparent py-3 font-display text-3xl text-chalk outline-none placeholder:text-steel/60"
              />
              {estimate.unit && <span className="shrink-0 font-display text-2xl text-steel">{estimate.unit}</span>}
            </label>
          </div>
          <button
            type="submit"
            disabled={!answering || !draft.trim()}
            className={`btn-3d btn-brand rounded-xl py-3 font-display text-2xl tracking-wide text-ink ${answering && draft.trim() ? '' : 'opacity-50'}`}
          >
            Chutar!
          </button>
          {error && <p className="text-center text-sm text-red-300">{error}</p>}
          <Waiting players={room.players} answered={estimate.answered} />
        </form>
      )}

      <LeaveButton onLeave={onLeave} />
    </section>
  )
}

function Waiting({ players, answered }: { players: PlayerView[]; answered: string[] }) {
  return (
    <ul className="flex flex-wrap justify-center gap-1.5" aria-label="Quem já chutou">
      {players.map((player) => (
        <li key={player.id} title={player.nickname}>
          <img
            src={AVATAR_URLS[player.avatar]}
            alt={player.nickname}
            className={`size-9 transition-opacity ${answered.includes(player.id) ? '' : 'opacity-30 grayscale'}`}
          />
        </li>
      ))}
    </ul>
  )
}

function guessLabel(guess: EstimateGuess, maxLoss: number) {
  if (guess.value === null) return 'Não chutou'
  if (guess.exact) return 'Chute certeiro!'
  if (guess.delta === maxLoss) return 'Chute pra lua'
  return `Errou por ${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(guess.error_percent ?? 0)}%`
}

function Reveal({ estimate, players, playerId, onSkip }: { estimate: EstimateView; players: PlayerView[]; playerId: string | null; onSkip: Props['onSkip'] }) {
  const [skipped, setSkipped] = useState(false)
  const byId = (id: string) => players.find((p) => p.id === id)
  const deltas = Object.fromEntries(estimate.guesses.map((g) => [g.player_id, g.delta]))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-1">
        <p className="text-sm font-semibold tracking-[0.3em] text-steel uppercase">Resposta</p>
        <p className="reveal-pop font-display text-5xl text-emerald-300">{withUnit(estimate.answer!, estimate.unit)}</p>
      </div>

      <Ruler estimate={estimate} players={players} playerId={playerId} />

      <ul className="flex flex-col gap-1.5" aria-label="Chutes">
        {estimate.guesses.map((guess, index) => {
          const player = byId(guess.player_id)
          return (
            <li
              key={guess.player_id}
              className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold ${
                guess.exact ? 'bg-brand/20 text-brand' : guess.delta > 0 ? 'bg-emerald-500/15 text-emerald-200' : 'bg-red-500/15 text-red-200'
              } ${guess.player_id === playerId ? 'ring-1 ring-brand/60' : ''}`}
              style={{ animationDelay: `${0.3 + index * 0.1}s` }}
            >
              {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />}
              <span className="flex min-w-0 flex-1 flex-col leading-tight">
                <span className="truncate">
                  {guess.player_id === playerId ? 'Você' : player?.nickname}
                  {guess.value !== null && `: ${withUnit(guess.value, estimate.unit)}`}
                </span>
                <span className="text-xs font-normal opacity-80">{guessLabel(guess, estimate.scoring.max_loss)}</span>
              </span>
              <span className="font-display text-lg">{formatDelta(guess.delta)}</span>
            </li>
          )
        })}
      </ul>

      {estimate.fact && <FactCard fact={estimate.fact} />}

      <Ranking players={players} playerId={playerId} deltas={deltas} />

      <button
        onClick={async () => {
          setSkipped(true)
          playSound('skip')
          await onSkip()
        }}
        disabled={skipped}
        className={`btn-3d btn-sm self-center rounded-xl px-5 py-2 font-semibold ${skipped ? 'btn-dark is-pressed text-steel' : 'btn-dark text-chalk'}`}
      >
        {skipped ? `Esperando (${estimate.ready.length}/${players.filter((p) => p.connected).length})` : 'Pular'}
      </button>
    </div>
  )
}

/** A régua: a resposta no meio, a zona em que o chute ganha QI e cada avatar no próprio chute. */
function Ruler({ estimate, players, playerId }: { estimate: EstimateView; players: PlayerView[]; playerId: string | null }) {
  const answer = estimate.answer!
  const reference = estimate.reference ?? (Math.abs(answer) || 1)
  const placed = estimate.guesses.filter((g) => g.value !== null)
  const { break_even_percent: breakEven, max_loss_percent: maxLoss } = estimate.scoring
  // A régua vai até onde a perda chega ao máximo; quem chutou mais longe fica na ponta, com seta.
  const farthest = Math.max(0, ...placed.map((g) => Math.abs(g.value! - answer)))
  const half = Math.min(Math.max(farthest, (reference * breakEven) / 100), (reference * maxLoss) / 100)
  const position = (value: number) => 50 + (Math.max(-half, Math.min(half, value - answer)) / half) * 46
  // Largura (em % da régua) da zona em que o chute ainda ganha QI.
  const gain = Math.min(92, ((reference * breakEven) / 100 / half) * 92)
  const sorted = [...placed].sort((a, b) => a.value! - b.value!)

  return (
    <div className="relative h-28 w-full" aria-hidden="true">
      {/* Fora da zona verde o chute perde QI; quanto mais vermelho, mais perde. */}
      <div className="absolute inset-x-[4%] top-16 h-3 rounded-full bg-gradient-to-r from-red-500/50 via-panel to-red-500/50" />
      <div
        className="absolute top-16 h-3 rounded-full"
        style={{
          left: `${50 - gain / 2}%`,
          width: `${gain}%`,
          background: 'linear-gradient(90deg, transparent, rgba(52, 211, 153, 0.75), transparent)',
        }}
      />
      <div className="absolute top-12 h-11 w-1 -translate-x-1/2 rounded-full bg-emerald-300" style={{ left: '50%' }} />
      {sorted.map((guess, index) => {
        const player = players.find((p) => p.id === guess.player_id)
        const off = Math.abs(guess.value! - answer) > half
        return (
          <div
            key={guess.player_id}
            className="avatar-pop absolute flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${position(guess.value!)}%`, top: index % 2 ? '1.6rem' : '0', animationDelay: `${0.2 + index * 0.08}s` }}
          >
            {player && (
              <img src={AVATAR_URLS[player.avatar]} alt="" className={`size-8 ${guess.player_id === playerId ? 'rounded-full ring-2 ring-brand' : ''}`} />
            )}
            {off && <span className="text-xs font-bold text-red-300">{guess.value! < answer ? '◀' : '▶'}</span>}
          </div>
        )
      })}
    </div>
  )
}
