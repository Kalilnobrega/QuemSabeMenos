import { useEffect, useState } from 'react'
import { avatarUrl } from '../lib/avatars'
import { useRemaining, useUrgentTick } from '../lib/effects'
import { DifficultyChip, PhaseTimer, TimerBar } from './RoundUI'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { EstimateGuess, EstimateView, PlayerView } from '../types/events'
import { formatDelta, formatEstimate } from '../lib/format'
import { AnsweredRow } from './Answered'
import { draftValue } from '../lib/guessDraft'
import { EstimateKeypad } from './EstimateKeypad'
import { EstimateRuler } from './EstimateRuler'
import { FactCard, Podium, Ranking } from './Game'
import { LevelIntro, SkipButton, StartScreen } from './Screens'
import { LeaveButton } from './LeaveButton'

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onGuess: (value: number) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

// A opção de poderes da sala pode vir ligada de outro modo. Ligar isto quando o Chutômetro tiver poderes:
// com eles, só o teclado da tela digita.
const ESTIMATE_HAS_POWERS = false

const ESTIMATE_LEVEL_LINES: Record<string, string> = {
  medium: 'Agora chegar perto vale mais QI.',
  hard: 'Vale muito QI, e chutar longe tira menos pontos.',
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
    return <LevelIntro difficulty={estimate.difficulty} line={ESTIMATE_LEVEL_LINES[estimate.difficulty]} />
  }
  // key: cada pergunta começa com o campo vazio.
  return (
    <EstimateRound
      key={estimate.round}
      snapshot={snapshot}
      playerId={playerId}
      onGuess={onGuess}
      onSkip={onSkip}
      onLeave={onLeave}
    />
  )
}

function withUnit(value: number, unit: string | null | undefined) {
  return unit ? `${formatEstimate(value, unit)} ${unit}` : formatEstimate(value, unit)
}

function EstimateStart({ snapshot }: { snapshot: Snapshot }) {
  const estimate = snapshot.room.estimate!
  return (
    <StartScreen
      room={snapshot.room}
      receivedAt={snapshot.receivedAt}
      endsInMs={estimate.phase_ends_in_ms}
      eyebrow="Chutômetro"
      rules={[`${estimate.total_rounds} perguntas de número.`, 'Chegou perto, ganha QI; chutou pra lua, perde.']}
    />
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
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const answering = estimate.phase === 'answering'
  const results = estimate.phase === 'results'
  const remaining = useRemaining(receivedAt, estimate.phase_ends_in_ms, answering || results)
  const guessed = estimate.my_guess !== null && estimate.my_guess !== undefined
  useUrgentTick(remaining, answering && !guessed)
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
    const value = draftValue(draft)
    if (value === null) return
    playSound('select')
    setError(await onGuess(value))
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
      {/* O alerta vem antes porque aqui ainda é preciso digitar o chute. */}
      {answering ? (
        <PhaseTimer remaining={remaining} duration={estimate.phase_duration_ms} urgentMs={5000} />
      ) : (
        <TimerBar
          fill={results ? remaining / Math.max(1, estimate.phase_duration_ms) : null}
          tone="muted"
          seconds={null}
        />
      )}

      {/* Menor enquanto o teclado está na tela, para o botão de chutar caber no celular. */}
      <h2
        className={`text-center font-display leading-tight tracking-wide ${results || guessed ? 'text-3xl' : 'text-2xl'}`}
      >
        {estimate.text}
      </h2>

      {results ? (
        <Reveal estimate={estimate} players={room.players} playerId={playerId} onSkip={onSkip} />
      ) : guessed ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-steel">Seu chute</p>
          <p className="font-display text-5xl text-brand">{withUnit(estimate.my_guess!, estimate.unit)}</p>
          <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <EstimateKeypad
            draft={draft}
            unit={estimate.unit}
            disabled={!answering}
            physicalKeys={!(ESTIMATE_HAS_POWERS && room.settings.powers)}
            onChange={setDraft}
            onSubmit={() => void submit()}
          />
          {error && <p className="text-center text-sm text-danger">{error}</p>}
          <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />
        </div>
      )}

      <LeaveButton onLeave={onLeave} />
    </section>
  )
}

function guessLabel(guess: EstimateGuess, maxLoss: number) {
  if (guess.value === null) return 'Não chutou'
  if (guess.exact) return 'Chute certeiro!'
  if (guess.delta === maxLoss) return 'Chute pra lua'
  return `Errou por ${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(guess.error_percent ?? 0)}%`
}

function Reveal({
  estimate,
  players,
  playerId,
  onSkip,
}: {
  estimate: EstimateView
  players: PlayerView[]
  playerId: string | null
  onSkip: Props['onSkip']
}) {
  const byId = (id: string) => players.find((p) => p.id === id)
  const deltas = Object.fromEntries(estimate.guesses.map((g) => [g.player_id, g.delta]))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-1">
        <p className="text-sm font-semibold tracking-[0.3em] text-steel uppercase">Resposta</p>
        <p className="reveal-pop font-display text-5xl text-success">{withUnit(estimate.answer!, estimate.unit)}</p>
      </div>

      <EstimateRuler estimate={estimate} players={players} playerId={playerId} />

      <ul className="flex flex-col gap-1.5" aria-label="Chutes">
        {estimate.guesses.map((guess, index) => {
          const player = byId(guess.player_id)
          return (
            <li
              key={guess.player_id}
              className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold ${
                guess.exact
                  ? 'bg-brand/20 text-brand'
                  : guess.delta > 0
                    ? 'bg-success-strong/15 text-success'
                    : 'bg-danger-strong/15 text-danger'
              } ${guess.player_id === playerId ? 'ring-1 ring-brand/60' : ''}`}
              style={{ animationDelay: `${0.3 + index * 0.1}s` }}
            >
              {player && <img src={avatarUrl(player)} alt="" className="size-7" />}
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

      <SkipButton
        ready={estimate.ready}
        players={players}
        playerId={playerId}
        onSkip={onSkip}
        endsInMs={estimate.phase_ends_in_ms}
        durationMs={estimate.phase_duration_ms}
      />
    </div>
  )
}
