import { useEffect, useState } from 'react'
import { avatarUrl } from '../lib/avatars'
import { useFlashbang, useRemaining, useUrgentTick, vibrate } from '../lib/effects'
import { ESTIMATE_HINTS, POWERUP_INFO, gainParts, scrambleWords, seededShuffle, type Kind } from '../lib/powerups'
import { DifficultyChip, PhaseTimer, TimerBar } from './RoundUI'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { EstimateGuess, EstimateView, PlayerView, PowerUpUse } from '../types/events'
import { formatDelta, formatEstimate } from '../lib/format'
import { AnsweredRow } from './Answered'
import { DIGIT_KEYS, draftValue } from '../lib/guessDraft'
import { EstimateKeypad } from './EstimateKeypad'
import { EstimateRuler } from './EstimateRuler'
import { CountUp, FactCard, Podium, Ranking } from './Game'
import { ActivePowerUps, InstantPowerUps, Magnifier, PowerUpBar, PowerUpIcon, ScratchCard } from './PowerUps'
import { BannerList, LevelIntro, StartScreen, type BannerItem } from './Screens'
import { LeaveButton } from './LeaveButton'

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onGuess: (value: number) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onArm: (
    kind: PowerUpUse['kind'],
    target: string | null,
    legendary?: boolean,
    theme?: string | null,
  ) => Promise<string | null>
  onDisarm: () => Promise<string | null>
  onUse: (kind: PowerUpUse['kind']) => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

const SELF_LINES: Partial<Record<Kind, string>> = {
  shield: 'Seu Escudo está ativo por até 2 perguntas: o primeiro chute que perderia QI não tira nada.',
  peek: 'Espiar: veja os chutes dos outros ao vivo.',
  second_chance: 'Segunda chance nesta e na próxima: se o chute perder QI, você tenta de novo.',
  investment: 'Investimento valendo: cada chute seguido que ganha QI rende mais!',
  range: 'Faixa: a resposta está no intervalo acima do teclado.',
  wide_margin: 'Margem larga: nesta pergunta, sua zona de ganho é o dobro.',
  hot_keys: 'Tecla quente: as teclas acesas são algarismos da resposta.',
}
const BROKEN_KEYS = 3
const HIT_LINES: Partial<Record<Kind, string>> = {
  accelerator: 'jogou Acelerador em você: um terço do tempo!',
  flashbang: 'jogou Flashbang em você: leia rápido, a pergunta some em 4 segundos!',
  broken_keys: 'jogou Tecla quebrada em você: 3 teclas vão rachar quando você tocar!',
  shuffled_keys: 'jogou Teclado mentiroso em você: as teclas trocaram de lugar!',
  perfectionist: 'jogou Perfeccionista em você: não dá para apagar!',
  nudge: 'jogou Empurrão em você: seu chute andou na régua!',
}
const HIT_DETAILS: Partial<Record<Kind, string>> = {
  accelerator: 'Um terço do tempo',
  mirror: 'A pergunta está espelhada',
  flashbang: 'Leia rápido: a pergunta some em 4 segundos',
  broken_keys: '3 teclas vão rachar quando você tocar',
  shuffled_keys: 'As teclas trocaram de lugar',
  perfectionist: 'Não dá para apagar: capriche',
  nudge: 'Seu chute andou na régua',
}

const ESTIMATE_LEVEL_LINES: Record<string, string> = {
  medium: 'Agora chegar perto vale mais QI.',
  hard: 'Vale muito QI, e chutar longe tira menos pontos.',
}

/** Chutômetro: a resposta é um número; quanto mais perto, mais QI. */
export function Estimate({ snapshot, playerId, onGuess, onSkip, onArm, onDisarm, onUse, onPlayAgain, onLeave }: Props) {
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
      onArm={onArm}
      onDisarm={onDisarm}
      onUse={onUse}
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
      power={estimate.starting_powerup ? { kind: estimate.starting_powerup } : null}
    />
  )
}

interface RoundProps {
  snapshot: Snapshot
  playerId: string | null
  onGuess: Props['onGuess']
  onSkip: Props['onSkip']
  onArm: Props['onArm']
  onDisarm: Props['onDisarm']
  onUse: Props['onUse']
  onLeave: Props['onLeave']
}

function EstimateRound({ snapshot, playerId, onGuess, onSkip, onArm, onDisarm, onUse, onLeave }: RoundProps) {
  const { room, receivedAt } = snapshot
  const estimate = room.estimate!
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const answering = estimate.phase === 'answering'
  const results = estimate.phase === 'results'
  const remaining = useRemaining(receivedAt, estimate.phase_ends_in_ms, answering || results)
  const guessed = estimate.my_guess !== null && estimate.my_guess !== undefined
  const silenced = estimate.silenced_rounds > 0
  useUrgentTick(remaining, answering && !guessed && !silenced)
  const mine = estimate.guesses.find((g) => g.player_id === playerId)
  const hits = (kind: Kind) => !results && estimate.active.some((use) => use.kind === kind && use.target === playerId)
  const blinded = useFlashbang(estimate.flashbang && answering, estimate.phase_duration_ms - remaining)
  const sabotaged = estimate.active.some((use) => POWERUP_INFO[use.kind].targeted && use.target === playerId)
  const text = hits('scramble') ? scrambleWords(estimate.text ?? '', estimate.round) : estimate.text

  useEffect(() => {
    if (answering) playSound('answersOpen')
  }, [answering])
  useEffect(() => {
    if (sabotaged && answering) playSound('powerHit')
    // Só quando a pergunta aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // Segunda chance: o campo volta vazio para o novo chute.
  useEffect(() => {
    if (estimate.first_guess === null) return
    setDraft('')
    playSound('wrong')
    vibrate(200)
  }, [estimate.first_guess])
  useEffect(() => {
    if (!results || !mine) return
    playSound(mine.shielded ? 'shield' : mine.value === null ? 'noAnswer' : mine.delta > 0 ? 'correct' : 'wrong')
    if (mine.delta !== 0) playSound('countUp', mine.delta)
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
    <section className={`flex w-full flex-col ${answering && !guessed ? 'gap-3' : 'gap-5'}`}>
      <header className="flex items-center justify-between gap-2 text-sm">
        <span className="font-semibold whitespace-nowrap text-steel">
          Pergunta {estimate.round}/{estimate.total_rounds}
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0 truncate rounded-full bg-panel px-2.5 py-1 text-steel">{estimate.theme}</span>
          <DifficultyChip difficulty={estimate.difficulty} />
        </span>
      </header>

      {blinded && <div className="flashbang-flash" aria-hidden="true" />}
      {estimate.powers && (
        <ActivePowerUps
          game={estimate}
          players={room.players}
          playerId={playerId}
          concealed={blinded}
          lines={SELF_LINES}
          hitLines={HIT_LINES}
          hitDetails={HIT_DETAILS}
        />
      )}
      {estimate.powers && answering && !guessed && !silenced && (
        <InstantPowerUps game={estimate} playerId={playerId} onUse={onUse} />
      )}

      {/* Na resposta, o tempo para chutar; na revelação, quanto falta para a próxima pergunta. */}
      {/* O alerta vem antes porque aqui ainda é preciso digitar o chute. */}
      {answering ? (
        <PhaseTimer
          remaining={remaining}
          duration={estimate.phase_duration_ms}
          urgentMs={5000}
          className={silenced ? 'invisible' : ''}
        />
      ) : (
        <TimerBar
          fill={results ? remaining / Math.max(1, estimate.phase_duration_ms) : null}
          tone="muted"
          seconds={null}
        />
      )}

      {/* Menor enquanto o teclado está na tela, para o botão de chutar caber no celular. */}
      <Magnifier active={hits('magnifier') && !blinded}>
        <ScratchCard active={hits('scratch') && !blinded}>
          <h2
            className={`text-center font-display leading-tight tracking-wide ${results || guessed ? 'text-3xl' : 'text-2xl'} ${hits('mirror') ? '-scale-x-100' : ''} ${blinded ? 'invisible' : ''}`}
          >
            {text}
          </h2>
        </ScratchCard>
      </Magnifier>

      {results ? (
        <Reveal
          estimate={estimate}
          players={room.players}
          playerId={playerId}
          onSkip={onSkip}
          onArm={onArm}
          onDisarm={onDisarm}
        />
      ) : guessed ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-steel">Seu chute</p>
          <p className="font-display text-5xl text-brand">{withUnit(estimate.my_guess!, estimate.unit)}</p>
          {!silenced && <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {estimate.first_guess !== null && (
            <p className="rounded-xl bg-panel px-3 py-2 text-center text-sm text-chalk">
              {withUnit(estimate.first_guess, estimate.unit)} perde QI. A resposta é{' '}
              <strong className="text-brand">{estimate.retry_hint === 'higher' ? 'mais alta' : 'mais baixa'}</strong>.
              Chute de novo, valendo metade!
            </p>
          )}
          {estimate.range_hint && (
            <p className="rounded-xl bg-panel px-3 py-2 text-center text-sm text-chalk">
              A resposta está entre{' '}
              <strong className="text-brand">{formatEstimate(estimate.range_hint.low, estimate.unit)}</strong> e{' '}
              <strong className="text-brand">{withUnit(estimate.range_hint.high, estimate.unit)}</strong>.
            </p>
          )}
          {estimate.peek && <PeekList peek={estimate.peek} players={room.players} unit={estimate.unit} />}
          <EstimateKeypad
            draft={draft}
            unit={estimate.unit}
            disabled={!answering}
            physicalKeys={!estimate.powers}
            compact={estimate.powers}
            hotDigits={estimate.hot_digits ?? []}
            brokenKeys={hits('broken_keys') ? seededShuffle(DIGIT_KEYS, estimate.round).slice(0, BROKEN_KEYS) : []}
            shuffleSeed={hits('shuffled_keys') ? estimate.round : null}
            noErase={hits('perfectionist')}
            onChange={setDraft}
            onSubmit={() => void submit()}
          />
          {error && <p className="text-center text-sm text-danger">{error}</p>}
          {!silenced && <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />}
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

/** Espiar: os chutes dos outros, ao vivo. */
function PeekList({
  peek,
  players,
  unit,
}: {
  peek: NonNullable<EstimateView['peek']>
  players: PlayerView[]
  unit: EstimateView['unit']
}) {
  if (peek.length === 0) return <p className="text-center text-sm text-steel">Espiando: ninguém chutou ainda.</p>
  return (
    <ul className="flex flex-wrap justify-center gap-1.5" aria-label="Chutes dos outros">
      {peek.map(({ player_id, value }) => {
        const player = players.find((p) => p.id === player_id)
        return (
          <li
            key={player_id}
            className="flex items-center gap-1 rounded-full bg-panel py-0.5 pr-2.5 pl-1 text-sm font-semibold"
          >
            {player && <img src={avatarUrl(player)} alt={player.nickname} className="size-6" />}
            {withUnit(value, unit)}
          </li>
        )
      })}
    </ul>
  )
}

function guessVerdict(guess: EstimateGuess) {
  if (guess.value === null) return 'Não chutou!'
  if (guess.exact) return 'Cravou!'
  return guess.delta > 0 ? 'Chegou perto!' : 'Passou longe!'
}

/** Quanto o QI mudou nesta pergunta, com os poderes. */
const guessTotal = (guess: EstimateGuess) => guess.delta + guess.investment + guess.stolen - guess.robbed

/** O que os poderes fizeram na revelação. */
function powerNotes(estimate: EstimateView, players: PlayerView[], playerId: string | null): BannerItem[] {
  const who = (id: string) => (id === playerId ? 'Você' : (players.find((p) => p.id === id)?.nickname ?? '?'))
  const notes: BannerItem[] = []
  for (const guess of estimate.guesses) {
    const id = guess.player_id
    const base = { player: players.find((p) => p.id === id), who: who(id), me: id === playerId }
    const note = (key: string, kind: Kind, title: string, detail: string, delta: number | null = null) =>
      notes.push({
        ...base,
        key: `${id}-${key}`,
        icon: <PowerUpIcon kind={kind} className="size-full" />,
        title,
        detail,
        delta,
        tone: POWERUP_INFO[kind].tone,
      })
    for (const kind of guess.expired) {
      note(`${kind}-expired`, kind, `${POWERUP_INFO[kind].name} quebrou`, 'Acabou sem ser usado')
    }
    if (guess.doubled) {
      note('double', 'double', 'Dobro!', guess.delta > 0 ? 'O ganho valeu o dobro' : 'A perda pesou mais', guess.delta)
    }
    if (guess.first_value !== null) {
      note(
        'second',
        'second_chance',
        guess.delta > 0 ? 'Salvou na segunda chance' : 'A segunda chance não salvou',
        `O primeiro chute foi ${withUnit(guess.first_value, estimate.unit)}`,
      )
    }
    if (guess.nudged_from !== null) {
      note('nudge', 'nudge', 'Levou um Empurrão', `O chute era ${withUnit(guess.nudged_from, estimate.unit)}`)
    }
    if (estimate.active.some((use) => use.kind === 'wide_margin' && use.by === id)) {
      note('wide', 'wide_margin', 'Margem larga', 'A zona de ganho dobrou')
    }
    if (guess.shielded) note('shield', 'shield', 'O Escudo segurou', `Salvou ${guess.shielded} de QI`)
    if (guess.investment) note('investment', 'investment', 'Investimento', 'Bônus do chute', guess.investment)
    for (const use of estimate.active) {
      if (use.kind !== 'steal' || use.by !== id) continue
      const target = use.target ? who(use.target) : '?'
      const whom = target === 'Você' ? 'você' : target
      note(
        'steal',
        'steal',
        guess.stolen ? `Roubou ${whom}` : `Roubo em ${whom} falhou`,
        guess.stolen ? `Levou ${guess.stolen} de QI` : 'O Escudo segurou',
        guess.stolen ? (use.target === playerId ? -guess.stolen : guess.stolen) : null,
      )
    }
    if (guess.gained) note('gain', guess.gained.kind, gainParts(guess.gained).title, gainParts(guess.gained).detail)
  }
  return notes
}

function Reveal({
  estimate,
  players,
  playerId,
  onSkip,
  onArm,
  onDisarm,
}: {
  estimate: EstimateView
  players: PlayerView[]
  playerId: string | null
  onSkip: Props['onSkip']
  onArm: Props['onArm']
  onDisarm: Props['onDisarm']
}) {
  const byId = (id: string) => players.find((p) => p.id === id)
  const deltas = Object.fromEntries(estimate.guesses.map((g) => [g.player_id, guessTotal(g)]))
  const bar = (
    <PowerUpBar
      powers={estimate.powers}
      game={estimate}
      players={players}
      playerId={playerId}
      hints={ESTIMATE_HINTS}
      lockedNote={
        estimate.silenced_rounds > 0 ? 'Silenciado: sem poderes por enquanto.' : 'Esta foi a última pergunta.'
      }
      onArm={onArm}
      onSkip={onSkip}
      onDisarm={onDisarm}
    />
  )
  if (estimate.silenced_rounds > 0) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-center font-hand text-lg font-medium text-steel">Silenciado: a revelação é surpresa.</p>
        {bar}
      </div>
    )
  }
  const notes = powerNotes(estimate, players, playerId)
  const mine = estimate.guesses.find((g) => g.player_id === playerId)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-1">
        <p className="text-sm font-semibold tracking-[0.3em] text-steel uppercase">Resposta</p>
        <p className="reveal-pop font-display text-5xl text-success">{withUnit(estimate.answer!, estimate.unit)}</p>
      </div>

      <EstimateRuler estimate={estimate} players={players} playerId={playerId} />

      {mine && (
        <p className="text-center font-display text-3xl tracking-wide">
          <span className={mine.delta > 0 ? 'text-success' : 'text-danger'}>{guessVerdict(mine)}</span>{' '}
          <span className="text-chalk">
            <CountUp from={0} to={mine.delta} format={formatDelta} /> QI
          </span>
        </p>
      )}

      {estimate.fact && <FactCard fact={estimate.fact} />}

      {bar}

      {notes.length > 0 && <BannerList items={notes} label="O que os poderes fizeram" />}

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
              <span className="font-display text-lg">{formatDelta(guessTotal(guess))}</span>
            </li>
          )
        })}
      </ul>

      <Ranking players={players} playerId={playerId} deltas={deltas} />
    </div>
  )
}
