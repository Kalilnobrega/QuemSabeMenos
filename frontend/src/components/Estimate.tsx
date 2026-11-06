import { useEffect, useState } from 'react'
import { avatarUrl } from '../lib/avatars'
import { useRemaining, useUrgentTick, vibrate } from '../lib/effects'
import { ESTIMATE_HINTS, POWERUP_INFO, gainParts, seededShuffle, shortCircuitMs, type Kind } from '../lib/powerups'
import { DifficultyChip, PhaseTimer, TimerBar } from './RoundUI'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { EstimateGuess, EstimateView, PlayerView, PowerUpUse } from '../types/events'
import { formatDelta, formatEstimate } from '../lib/format'
import { AnsweredRow } from './Answered'
import { DIGIT_KEYS, draftValue, formatDraft } from '../lib/guessDraft'
import { EstimateKeypad, MathKeypad, MathWatchPanel } from './EstimateKeypad'
import { EstimateRuler } from './EstimateRuler'
import { CountUp, FactCard, Podium, Ranking } from './Game'
import { ActivePowerUps, InstantPowerUps, PowerUpBar, PowerUpIcon, ScratchCard } from './PowerUps'
import { BannerList, LevelIntro, StartScreen, type BannerItem } from './Screens'
import { LeaveButton } from './LeaveButton'
import { MatchAwards } from './MatchAwards'
import { LastWordResultScene, LastWordScene, MathScene } from './MythicScenes'

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onGuess: (value: number) => Promise<string | null>
  onMathSteps: (steps: number[]) => Promise<string | null>
  onLastWordDraft: (draft: string) => Promise<string | null>
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
  copy: 'Cópia: chute normalmente. Se alguém chegar mais perto, você fica com o chute dessa pessoa.',
  second_chance: 'Segunda chance nesta e na próxima: se o chute perder QI, você tenta de novo.',
  range: 'Faixa: a resposta está no intervalo acima do teclado.',
  wide_margin: 'Margem larga: nesta pergunta, sua zona de ganho é o dobro.',
  hot_keys: 'Tecla quente: as teclas acesas são algarismos da resposta.',
  sniper: 'Sniper: zona de ganho pela metade e ganho em dobro. Mire bem!',
  last_word: 'Palavra final: você chuta por último. É tudo ou nada!',
}
const BROKEN_KEYS = 3
const MATH_SCENE_WINDOW_MS = 1500
const DOUBLE_KEYS = 3
const HIT_LINES: Partial<Record<Kind, string>> = {
  scratch: 'jogou Raspadinha em você! Raspe a pergunta e o teclado.',
  short_circuit: 'jogou Curto-circuito em você: seu teclado vai queimar. Chute logo!',
  double_click: 'jogou Duplo clique em você: 3 teclas digitam duas vezes. Olhe o visor!',
  math: 'jogou Matemática em você: você tem 30 segundos para fazer as contas!',
  broken_keys: 'jogou Tecla quebrada em você: 3 teclas vão rachar quando você tocar!',
  shuffled_keys: 'jogou Teclado mentiroso em você: as teclas trocaram de lugar!',
  perfectionist: 'jogou Perfeccionista em você: não dá para apagar!',
  nudge: 'jogou Empurrão em você: seu chute andou na régua!',
  swap: 'jogou Troca-troca em você: os chutes trocaram de lugar!',
  runaway_keys: 'jogou Teclas fugitivas em você: pegue as teclas e arraste cada uma para o espaço dela!',
}
const HIT_DETAILS: Partial<Record<Kind, string>> = {
  mirror: 'A pergunta está espelhada',
  scratch: 'Raspe a pergunta e o teclado',
  short_circuit: 'Seu teclado vai queimar. Chute logo!',
  double_click: '3 teclas digitam duas vezes. Olhe o visor!',
  math: 'Você tem 30 segundos para chegar na resposta, e a galera assiste',
  broken_keys: '3 teclas vão rachar quando você tocar',
  shuffled_keys: 'As teclas trocaram de lugar',
  perfectionist: 'Não dá para apagar: capriche',
  nudge: 'Seu chute andou na régua',
  swap: 'Os chutes trocaram de lugar',
  runaway_keys: 'Pegue as teclas e arraste cada uma para o espaço dela',
}

const ESTIMATE_LEVEL_LINES: Record<string, string> = {
  medium: 'Agora chegar perto vale mais QI.',
  hard: 'Vale muito QI, e chutar longe tira menos pontos.',
}

/** Chutômetro: a resposta é um número; quanto mais perto, mais QI. */
export function Estimate({
  snapshot,
  playerId,
  onGuess,
  onMathSteps,
  onLastWordDraft,
  onSkip,
  onArm,
  onDisarm,
  onUse,
  onPlayAgain,
  onLeave,
}: Props) {
  const estimate = snapshot.room.estimate!
  if (estimate.phase === 'finished') {
    return (
      <Podium
        room={snapshot.room}
        playerId={playerId}
        onPlayAgain={onPlayAgain}
        onLeave={onLeave}
        extra={<MatchAwards awards={estimate.awards} players={snapshot.room.players} playerId={playerId} />}
      />
    )
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
      onMathSteps={onMathSteps}
      onLastWordDraft={onLastWordDraft}
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
  onMathSteps: Props['onMathSteps']
  onLastWordDraft: Props['onLastWordDraft']
  onSkip: Props['onSkip']
  onArm: Props['onArm']
  onDisarm: Props['onDisarm']
  onUse: Props['onUse']
  onLeave: Props['onLeave']
}

function EstimateRound({
  snapshot,
  playerId,
  onGuess,
  onMathSteps,
  onLastWordDraft,
  onSkip,
  onArm,
  onDisarm,
  onUse,
  onLeave,
}: RoundProps) {
  const { room, receivedAt } = snapshot
  const estimate = room.estimate!
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const answering = estimate.phase === 'answering'
  const results = estimate.phase === 'results'
  const remaining = useRemaining(receivedAt, estimate.phase_ends_in_ms, answering || results)
  const guessed = estimate.my_guess !== null && estimate.my_guess !== undefined
  const silenced = estimate.silenced_rounds > 0
  const lastWord = estimate.last_word
  const speaking = lastWord?.player_id === playerId
  const lastWordOpen = !!lastWord?.open
  // Cenas dos míticos: cada uma toca uma vez por pergunta (o componente recomeça a cada pergunta).
  const [scenesDone, setScenesDone] = useState<string[]>([])
  const sceneDone = (scene: string) => () => setScenesDone((done) => [...done, scene])
  const mathUse = answering ? estimate.active.find((use) => use.kind === 'math') : undefined
  // Quem volta para a sala com a pergunta já andando não vê a cena de novo.
  const mathJustStarted = estimate.phase_duration_ms - remaining < MATH_SCENE_WINDOW_MS
  const speakerResult = results
    ? estimate.guesses.find(
        (g) => g.last_word && estimate.active.some((use) => use.kind === 'last_word' && use.by === g.player_id),
      )
    : undefined
  const playerById = (id: string | null | undefined) => room.players.find((p) => p.id === id)
  useUrgentTick(remaining, answering && !guessed && !estimate.time_up && !silenced && (!speaking || lastWordOpen))
  const mine = estimate.guesses.find((g) => g.player_id === playerId)
  // A sabotagem lendária não tem alvo: pega todos menos quem jogou.
  const hitsMe = (use: PowerUpUse) => (use.legendary ? use.by !== playerId : use.target === playerId)
  const hits = (kind: Kind) => !results && estimate.active.some((use) => use.kind === kind && hitsMe(use))
  const shorted =
    answering && hits('short_circuit') && estimate.phase_duration_ms - remaining >= shortCircuitMs(estimate.round)
  const sabotaged = estimate.active.some((use) => POWERUP_INFO[use.kind].targeted && hitsMe(use))

  useEffect(() => {
    if (answering) playSound('answersOpen')
  }, [answering])
  // Palavra final: chegou a vez, e a sala assiste ao que é digitado.
  useEffect(() => {
    if (speaking && lastWordOpen) playSound('powerHit')
  }, [speaking, lastWordOpen])
  useEffect(() => {
    if (speaking && lastWordOpen && draft) void onLastWordDraft(draft)
    // Só quando o rascunho muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])
  useEffect(() => {
    if (!shorted || guessed) return
    playSound('keyShort')
    vibrate([80, 40, 120])
    // Só quando o teclado queima.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shorted])
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

  const send = async (value: number) => {
    playSound('select')
    setError(await onGuess(value))
  }
  const submit = () => {
    const value = draftValue(draft)
    if (value !== null) void send(value)
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

      {estimate.powers && (
        <ActivePowerUps
          game={estimate}
          players={room.players}
          playerId={playerId}
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
      <ScratchCard active={hits('scratch')}>
        <h2
          className={`text-center font-display leading-tight tracking-wide ${results || guessed ? 'text-3xl' : 'text-2xl'} ${hits('mirror') ? '-scale-x-100' : ''}`}
        >
          {estimate.text}
        </h2>
      </ScratchCard>

      {results ? (
        <Reveal
          estimate={estimate}
          players={room.players}
          playerId={playerId}
          onSkip={onSkip}
          onArm={onArm}
          onDisarm={onDisarm}
        />
      ) : guessed || estimate.time_up ? (
        <div className="flex flex-col items-center gap-3">
          {guessed ? (
            <>
              <p className="text-steel">Seu chute</p>
              <p className="font-display text-5xl text-brand">{withUnit(estimate.my_guess!, estimate.unit)}</p>
            </>
          ) : (
            <p className="font-display text-2xl text-danger">Seu tempo acabou!</p>
          )}
          {lastWord && !speaking && (
            <LastWordPanel lastWord={lastWord} players={room.players} playerId={playerId} unit={estimate.unit} />
          )}
          {estimate.math_watch.map(({ player_id, math }) => (
            <MathWatchPanel
              key={player_id}
              math={math}
              unit={estimate.unit}
              player={room.players.find((p) => p.id === player_id)}
            />
          ))}
          {!silenced && <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />}
        </div>
      ) : speaking && !lastWordOpen ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-center font-display text-2xl text-brand">A palavra final é sua!</p>
          <p className="text-center text-sm text-steel">
            Quando todos chutarem, você vê os chutes e de que lado está a resposta, e tem 10 segundos.
          </p>
          <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {lastWord && speaking && (
            <LastWordPanel lastWord={lastWord} players={room.players} playerId={playerId} unit={estimate.unit} />
          )}
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
          {estimate.math ? (
            <MathKeypad
              puzzle={estimate.math}
              unit={estimate.unit}
              covered={hits('scratch')}
              shorted={shorted}
              onSteps={(steps) => void onMathSteps(steps)}
              onSubmit={(value) => void send(value)}
            />
          ) : (
            <EstimateKeypad
              draft={draft}
              unit={estimate.unit}
              disabled={!answering}
              physicalKeys={!estimate.powers}
              compact={estimate.powers}
              hotDigits={estimate.hot_digits ?? []}
              brokenKeys={hits('broken_keys') ? seededShuffle(DIGIT_KEYS, estimate.round).slice(0, BROKEN_KEYS) : []}
              doubleKeys={
                hits('double_click') ? seededShuffle(DIGIT_KEYS, estimate.round + 50).slice(0, DOUBLE_KEYS) : []
              }
              shuffleSeed={hits('shuffled_keys') ? estimate.round : null}
              noErase={hits('perfectionist')}
              covered={hits('scratch')}
              shorted={shorted}
              runaway={hits('runaway_keys')}
              onChange={setDraft}
              onSubmit={submit}
            />
          )}
          {error && <p className="text-center text-sm text-danger">{error}</p>}
          {!silenced && <AnsweredRow players={room.players} answered={estimate.answered} label="chutaram" />}
        </div>
      )}

      {mathUse && mathJustStarted && !scenesDone.includes('math') && (
        <MathScene target={playerById(mathUse.target)} isMe={mathUse.target === playerId} onDone={sceneDone('math')} />
      )}
      {lastWord && lastWordOpen && !scenesDone.includes('last-word') && (
        <LastWordScene speaker={playerById(lastWord.player_id)} isMe={speaking} onDone={sceneDone('last-word')} />
      )}
      {speakerResult && !scenesDone.includes('last-word-result') && (
        <LastWordResultScene
          speaker={playerById(speakerResult.player_id)}
          isMe={speakerResult.player_id === playerId}
          amount={speakerResult.last_word}
          onDone={sceneDone('last-word-result')}
        />
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

const LAST_WORD_SIDE = { higher: '↑ mais alta', lower: '↓ mais baixa', exact: 'Cravou!' }

/** Palavra final: os chutes e de que lado está a resposta; para a sala, também o que está sendo digitado. */
function LastWordPanel({
  lastWord,
  players,
  playerId,
  unit,
}: {
  lastWord: NonNullable<EstimateView['last_word']>
  players: PlayerView[]
  playerId: string | null
  unit: EstimateView['unit']
}) {
  const speaking = lastWord.player_id === playerId
  const speaker = players.find((p) => p.id === lastWord.player_id)
  if (!lastWord.open) {
    return <p className="text-center text-sm text-steel">{speaker?.nickname} tem a palavra final e chuta por último.</p>
  }
  return (
    <div className="mythic flex w-full flex-col gap-2 rounded-xl p-3">
      <p className="text-center font-display text-lg tracking-wide">
        {speaking ? 'Chegue mais perto que todos!' : `A palavra final de ${speaker?.nickname}`}
      </p>
      {!speaking && (
        <p className="text-center font-display text-4xl" aria-live="polite">
          {lastWord.draft ? formatDraft(lastWord.draft) : '…'}
          {unit && <span className="ml-2 font-sans text-sm font-semibold">{unit}</span>}
        </p>
      )}
      <ul className="flex flex-col gap-1" aria-label="Chutes dos outros">
        {lastWord.guesses.map(({ player_id, value, side }) => {
          const player = players.find((p) => p.id === player_id)
          return (
            <li
              key={player_id}
              className="flex items-center gap-2 rounded-lg bg-ink/40 px-2 py-1 text-sm font-semibold"
            >
              {player && <img src={avatarUrl(player)} alt="" className="size-6" />}
              <span className="min-w-0 flex-1 truncate">{withUnit(value, unit)}</span>
              <span className="whitespace-nowrap">{LAST_WORD_SIDE[side]}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function guessVerdict(guess: EstimateGuess) {
  if (guess.value === null) return 'Não chutou!'
  if (guess.exact) return 'Cravou!'
  return guess.delta > 0 ? 'Chegou perto!' : 'Passou longe!'
}

/** Quanto o QI mudou nesta pergunta, com os poderes. */
const guessTotal = (guess: EstimateGuess) => guess.delta + guess.stolen - guess.robbed + guess.last_word

/** O que os poderes fizeram na revelação. */
function powerNotes(estimate: EstimateView, players: PlayerView[], playerId: string | null): BannerItem[] {
  const who = (id: string) => (id === playerId ? 'Você' : (players.find((p) => p.id === id)?.nickname ?? '?'))
  const notes: BannerItem[] = []
  for (const guess of estimate.guesses) {
    const id = guess.player_id
    const base = { player: players.find((p) => p.id === id), who: who(id), me: id === playerId }
    const note = (
      key: string,
      kind: Kind,
      title: string,
      detail: string,
      delta: number | null = null,
      tone = POWERUP_INFO[kind].tone,
    ) =>
      notes.push({
        ...base,
        key: `${id}-${key}`,
        icon: <PowerUpIcon kind={kind} className="size-full" />,
        title,
        detail,
        delta,
        tone,
      })
    for (const kind of guess.expired) {
      note(`${kind}-expired`, kind, `${POWERUP_INFO[kind].name} quebrou`, 'Acabou sem ser usado')
    }
    if (guess.doubled) {
      const outcome = guess.exact
        ? 'O ganho dobrou, mas o bônus de cravar não'
        : guess.delta > 0
          ? 'O ganho valeu o dobro'
          : 'A perda pesou mais'
      note('double', 'double', 'Dobro!', outcome, guess.delta)
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
    if (guess.last_word) {
      const speaker = estimate.active.some((use) => use.kind === 'last_word' && use.by === id)
      note(
        'last-word',
        'last_word',
        speaker ? (guess.last_word > 0 ? 'A palavra final venceu' : 'A palavra final perdeu') : 'Palavra final',
        speaker
          ? guess.last_word > 0
            ? 'Chegou mais perto que todos'
            : 'Não chegou mais perto que todos'
          : guess.last_word > 0
            ? 'Recebeu de quem falou por último'
            : 'Pagou para quem falou por último',
        guess.last_word,
        'mythic',
      )
    }
    if (guess.copied_from) {
      note(
        'copy',
        'copy',
        `Copiou ${who(guess.copied_from) === 'Você' ? 'você' : who(guess.copied_from)}`,
        `O chute era ${withUnit(guess.copied_own ?? 0, estimate.unit)}`,
      )
    }
    if (guess.swapped_from !== null) {
      note('swap', 'swap', 'Troca-troca', `O chute era ${withUnit(guess.swapped_from, estimate.unit)}`)
    }
    if (estimate.active.some((use) => use.kind === 'sniper' && use.by === id)) {
      note('sniper', 'sniper', 'Sniper', guess.delta > 0 ? 'O ganho valeu o dobro' : 'Fora da zona menor', guess.delta)
    }
    if (estimate.active.some((use) => use.kind === 'wide_margin' && use.by === id)) {
      note('wide', 'wide_margin', 'Margem larga', 'A zona de ganho dobrou')
    }
    if (guess.shielded) note('shield', 'shield', 'O Escudo segurou', `Salvou ${guess.shielded} de QI`)
    for (const use of estimate.active) {
      if (use.kind !== 'steal' || use.by !== id) continue
      if (use.legendary) {
        note('steal', 'steal', 'Roubo lendário', `Levou ${guess.stolen} de QI dos outros`, guess.stolen)
        continue
      }
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
    if (guess.gained) {
      const { kind, mythic, legendary } = guess.gained
      const { title, detail } = gainParts(guess.gained)
      note('gain', kind, title, detail, null, mythic ? 'mythic' : legendary ? 'legendary' : undefined)
    }
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
