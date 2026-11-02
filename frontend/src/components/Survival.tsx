import { useEffect, useRef, useState, type ReactNode } from 'react'
import { avatarUrl } from '../lib/avatars'
import { reducedMotion, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import { POWERUP_INFO, SURVIVAL_HINTS, gainParts, scrambleWords, type Kind } from '../lib/powerups'
import type { PowerUpUse, Stab, SurvivalView, Survivor } from '../types/events'
import { AnsweredAvatar } from './Answered'
import { DaggerStrike } from './DaggerStrike'
import { ResurrectionScene } from './ResurrectionScene'
import { PeekBadge } from './Game'
import { BannerList, LevelIntro, PlayerPodium, StartScreen, type BannerItem } from './Screens'
import { ActivePowerUps, InstantPowerUps, Magnifier, PowerUpBar, PowerUpIcon, ScratchCard } from './PowerUps'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']
const DIFFICULTY_CHIP: Record<string, string> = {
  easy: 'bg-emerald-500/15 text-emerald-300',
  medium: 'bg-brand/15 text-brand',
  hard: 'bg-red-500/15 text-red-300',
  impossible: 'bg-orange-500/20 text-orange-300',
}

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number) => Promise<string | null>
  onArm: (kind: PowerUpUse['kind'], target: string | null, legendary?: boolean, theme?: string | null) => Promise<string | null>
  onUse: (kind: PowerUpUse['kind']) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onDisarm: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Último de pé: Verdadeiro ou Falso com vidas; quando sobram dois, X1 com o tempo caindo. */
export function Survival({ snapshot, playerId, onAnswer, onArm, onDisarm, onUse, onSkip, onPlayAgain, onLeave }: Props) {
  const survival = snapshot.room.survival!
  switch (survival.phase) {
    case 'starting':
      return <SurvivalStart snapshot={snapshot} />
    case 'level':
      return <LevelIntro difficulty={survival.difficulty} line={levelLine(survival)} />
    case 'duel_intro':
      return <DuelIntro snapshot={snapshot} playerId={playerId} />
    case 'finished':
      return <SurvivalPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
    default:
      // key: cada frase começa com a escolha local zerada.
      return <Statement key={survival.round} snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} onArm={onArm} onDisarm={onDisarm} onUse={onUse} onSkip={onSkip} />
  }
}

function HeartIcon({ full, className }: { full: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 24 22" className={className} aria-hidden="true">
      <path
        d="M12 20.5 3.2 12A5.4 5.4 0 0 1 12 4.6 5.4 5.4 0 0 1 20.8 12Z"
        fill={full ? '#F87171' : 'none'}
        stroke={full ? '#12141B' : '#6B7280'}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {full && <path d="M7.2 8.6a2.6 2.6 0 0 1 2.4-1.5" fill="none" stroke="#FECACA" strokeWidth="1.6" strokeLinecap="round" />}
    </svg>
  )
}

function Hearts({ lives, max, className = 'size-4' }: { lives: number; max: number; className?: string }) {
  return (
    <span className="flex gap-0.5" aria-label={`${lives} de ${max} vidas`}>
      {Array.from({ length: max }, (_, i) => (
        <HeartIcon key={i} full={i < lives} className={className} />
      ))}
    </span>
  )
}

function useRemaining(snapshot: Snapshot, active = true) {
  const now = useNow(active)
  return Math.max(0, snapshot.receivedAt + snapshot.room.survival!.phase_ends_in_ms - now)
}

function SurvivalStart({ snapshot }: { snapshot: Snapshot }) {
  const { room } = snapshot
  const survival = room.survival!
  return (
    <StartScreen
      room={room}
      receivedAt={snapshot.receivedAt}
      endsInMs={survival.phase_ends_in_ms}
      eyebrow="Último de pé"
      rules={[
        <>
          {survival.kind === 'true_false' ? 'Verdadeiro ou falso' : 'Alternativas'} · <Hearts lives={survival.max_lives} max={survival.max_lives} /> {survival.max_lives} vidas
        </>,
        <>
          {survival.easy_count > 0 && `${survival.easy_count} fáceis, `}
          {survival.medium_count} médias, depois só difíceis
        </>,
        'Sobraram dois? X1 até alguém errar!',
      ]}
      power={survival.starting_powerup ? { kind: survival.starting_powerup } : null}
    />
  )
}

const LEVELS: Record<string, { title: string; className: string }> = {
  easy: { title: 'Fácil', className: 'text-emerald-300 [text-shadow:0_4px_0_#065f46]' },
  medium: { title: 'Média', className: 'text-brand [text-shadow:0_4px_0_#7a5a00]' },
  hard: { title: 'Difícil', className: 'text-red-300 [text-shadow:0_4px_0_#7f1d1d]' },
  impossible: { title: 'Impossível', className: 'text-orange-300 [text-shadow:0_4px_0_#7c2d12]' },
}

function levelLine(survival: SurvivalView) {
  const what = survival.kind === 'true_false' ? 'frases' : 'perguntas'
  return survival.difficulty === 'hard' ? `Acabou a moleza: agora só ${what} difíceis.` : `Agora as ${what} apertam.`
}

function DuelIntro({ snapshot, playerId }: { snapshot: Snapshot; playerId: string | null }) {
  const { room } = snapshot
  const fighters = room.survival!.duelists.map((id) => room.players.find((p) => p.id === id))
  useSoundsOnMount([
    ['impossible', 0],
    ['duelIntro', 850],
    ['duelFight', 1650],
  ])
  useEffect(() => vibrate([0, 950, 120]), [])
  return (
    <div className="duel-intro" aria-label="X1!">
      <div className="relative flex items-center justify-center">
        {!reducedMotion() && <span className="duel-burst" />}
        <PowerUpIcon kind="duel" className="duel-clash relative size-28" />
      </div>
      <p className="intro-slam font-display text-7xl text-brand [text-shadow:0_5px_0_#7a5a00] [animation-delay:1.1s]">X1!</p>
      <div className="flex w-full max-w-sm items-center justify-between px-6">
        {fighters.map((p, i) =>
          p ? (
            <div key={p.id} className={`flex flex-col items-center gap-1 ${i === 0 ? 'duel-in-left' : 'duel-in-right'}`}>
              <img src={avatarUrl(p)} alt="" className="size-20" />
              <span className="max-w-32 truncate font-display text-2xl tracking-wide text-chalk">{p.id === playerId ? 'Você' : p.nickname}</span>
            </div>
          ) : null,
        )}
      </div>
      <p className="intro-step font-hand text-lg font-medium text-chalk" style={{ animationDelay: '1.6s' }}>
        Errou sozinho, perdeu. O tempo cai a cada frase!
      </p>
    </div>
  )
}

function Statement({ snapshot, playerId, onAnswer, onArm, onDisarm, onUse, onSkip }: { snapshot: Snapshot; playerId: string | null } & Pick<Props, 'onAnswer' | 'onArm' | 'onDisarm' | 'onUse' | 'onSkip'>) {
  const { room } = snapshot
  const survival = room.survival!
  const duel = survival.duelists.length > 0
  const choices = survival.kind === 'choices'
  const noun = choices ? 'Pergunta' : 'Frase'
  const reading = survival.phase === 'reading' || survival.phase === 'duel_reading'
  const open = survival.phase === 'answering' || survival.phase === 'duel_answering'
  const revealed = survival.phase === 'results' || survival.phase === 'duel_results'
  const remaining = useRemaining(snapshot, open)
  const [choice, setChoice] = useState<number | null>(survival.my_answer)
  const [error, setError] = useState<string | null>(null)
  const me = survival.survivors.find((s) => s.player_id === playerId)
  const answering = duel ? survival.duelists.includes(playerId ?? '') : !!me && me.out_round === null
  const answered = choice !== null
  const canAnswer = open && answering && !answered && !survival.hiding
  const silenced = survival.silenced_rounds > 0
  const myPick = survival.picks.find((p) => p.player_id === playerId)
  const player = (id: string) => room.players.find((p) => p.id === id)
  const name = (id: string | null | undefined) => (id === playerId ? 'você' : (player(id ?? '')?.nickname ?? '?'))

  const hits = (kind: PowerUpUse['kind']) => !revealed && survival.active.some((use) => use.kind === kind && use.target === playerId)
  const blinded = survival.flashbang && open && survival.phase_duration_ms - remaining >= FLASHBANG_MS
  const scrambled = hits('scramble')
  const mirrored = hits('mirror') ? '-scale-x-100' : ''
  const scratched = hits('scratch') && !blinded
  const sabotaged = survival.active.some((use) => use.kind !== 'steal' && TARGETED.has(use.kind) && use.target === playerId)
  const text = scrambled ? scrambleWords(survival.text ?? '', survival.round) : survival.text

  useEffect(() => {
    if (open) playSound('answersOpen')
  }, [open])
  useEffect(() => {
    if (sabotaged && !revealed) playSound('powerHit')
    // Só quando a pergunta aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])
  const myOutcome = myPick ? (myPick.correct ? 'correct' : myPick.option === null ? 'noAnswer' : 'wrong') : null
  useEffect(() => {
    if (!myOutcome) return
    playSound(myOutcome)
    if (myOutcome !== 'correct') vibrate(200)
  }, [myOutcome])
  // Cada Adaga nova vira uma cena; quem entra no meio da revelação não revê as de antes.
  const seenStabs = useRef(survival.stabs.length)
  const [strikes, setStrikes] = useState<{ id: number; stab: Stab }[]>([])
  useEffect(() => {
    const seen = seenStabs.current
    if (survival.stabs.length <= seen) return
    seenStabs.current = survival.stabs.length
    setStrikes((queue) => [...queue, ...survival.stabs.slice(seen).map((stab, i) => ({ id: seen + i, stab }))])
  }, [survival.stabs])

  const pick = async (option: number) => {
    if (!canAnswer || survival.hidden_options.includes(option)) return
    playSound('select')
    setChoice(option)
    const failure = await onAnswer(option)
    if (failure) {
      setChoice(null)
      setError(failure)
    }
  }
  const picksOn = (index: number) => survival.picks.filter((k) => k.option === index).map((k) => player(k.player_id))

  let status: ReactNode = ''
  if (reading) {
    status = 'Leia com calma…'
  } else if (open) {
    if (!answering) status = duel ? 'Torça pelo seu lado!' : survival.powers ? 'Você é fantasma: assiste e sabota quem está vivo.' : 'Você está fora. Assiste aí!'
    else if (survival.hiding) status = 'Esconderijo: você pula esta pergunta sem perder vida.'
    else if (survival.blessing !== null && !answered) status = <span className="text-yellow-200">Bênção: a certa está brilhando!</span>
    else if (blinded && !answered) status = 'Flashbang! Agora é chutar pela letra.'
    else if (answered) status = 'Resposta enviada!'
    else status = silenced ? 'Silêncio… quanto tempo será que falta?' : duel ? 'Errou sozinho, perdeu!' : 'Errar ou não responder tira uma vida.'
  } else if (silenced && survival.phase === 'results') {
    status = 'Silenciado: a revelação é surpresa.'
  } else if (survival.spared) {
    status = 'Todo mundo errou: ninguém perde vida!'
  } else if (myPick) {
    const out = me?.out_round !== null
    status = myPick.hidden ? (
      <span className="text-emerald-300">Você ficou escondido nesta.</span>
    ) : myPick.correct && !myPick.pact_from ? (
      <span className="text-emerald-300">Acertou!</span>
    ) : myPick.shielded ? (
      <span className="text-sky-300">O Escudo segurou sua vida!</span>
    ) : (
      <span className="text-red-300">
        {out ? 'Você caiu!' : myPick.cursed ? 'Maldição: perdeu 2 vidas!' : myPick.pact_from && myPick.correct ? 'Acertou, mas o Pacto de sangue cobrou uma vida!' : 'Perdeu uma vida!'}
        {myPick.stolen_by && ` E ${name(myPick.stolen_by)} ficou com ela.`}
      </span>
    )
  }

  // Acontecimentos da revelação, no mesmo banner dos outros modos.
  const icon = (kind: Kind) => <PowerUpIcon kind={kind} className="size-full" />
  const tone = (kind: Kind) => POWERUP_INFO[kind].tone
  const notes: BannerItem[] = [
    ...survival.revived.map((id) => ({ key: `revived-${id}`, player: player(id), icon: icon('resurrection'), who: cap(name(id)), title: 'Ressuscitou', detail: 'Voltou com 1 vida', tone: 'mythic', me: id === playerId })),
    ...survival.stabs.map((s) => ({
      key: `stab-${s.by}-${s.target}`,
      player: player(s.by),
      icon: icon('dagger'),
      who: cap(name(s.by)),
      title: `Cravou a Adaga em ${name(s.target)}`,
      detail: s.eliminated ? `Eliminou e ${s.by === playerId ? 'você ganhou' : 'ganhou'} a Bênção na próxima` : 'Tirou 1 vida',
      tone: 'mythic',
      me: s.by === playerId || s.target === playerId,
    })),
    ...survival.picks
      .filter((p) => p.cursed && p.player_id !== playerId)
      .map((p) => ({ key: `curse-${p.player_id}`, player: player(p.player_id), icon: icon('curse'), who: cap(name(p.player_id)), title: 'Perdeu 2 vidas', detail: 'Maldição', tone: tone('curse') })),
    ...survival.picks
      .filter((p) => p.pact_from && p.player_id !== playerId)
      .map((p) => ({
        key: `pact-${p.player_id}`,
        player: player(p.player_id),
        icon: icon('blood_pact'),
        who: cap(name(p.player_id)),
        title: 'Perdeu uma vida junto',
        detail: `Pacto de sangue com ${name(p.pact_from)}`,
        tone: tone('blood_pact'),
      })),
    ...survival.picks
      .filter((p) => p.hidden && p.player_id !== playerId)
      .map((p) => ({ key: `hide-${p.player_id}`, player: player(p.player_id), icon: icon('hide'), who: cap(name(p.player_id)), title: 'Ficou escondido', detail: 'Pulou esta sem perder vida', tone: tone('hide') })),
    ...survival.picks
      .filter((p) => p.stolen_by && p.player_id !== playerId)
      .map((p) => ({
        key: `steal-${p.player_id}`,
        player: player(p.stolen_by ?? ''),
        icon: icon('steal'),
        who: cap(name(p.stolen_by)),
        title: `Roubou uma vida de ${name(p.player_id)}`,
        detail: 'Roubo de vida',
        tone: tone('steal'),
        me: p.stolen_by === playerId,
      })),
    ...survival.picks
      .filter((p) => p.shielded && p.player_id !== playerId)
      .map((p) => ({ key: `shield-${p.player_id}`, player: player(p.player_id), icon: icon('shield'), who: cap(name(p.player_id)), title: 'O Escudo segurou', detail: 'Não perdeu vida', tone: tone('shield') })),
    ...survival.gifts.map((g) => ({
      key: `gift-${g.player_id}-${g.gain.kind}`,
      player: player(g.player_id),
      icon: icon(g.gain.kind),
      who: cap(name(g.player_id)),
      ...gainParts(g.gain),
      tone: g.gain.mythic ? 'mythic' : g.gain.legendary ? 'legendary' : tone(g.gain.kind),
      me: g.player_id === playerId,
    })),
  ]

  return (
    <section className="flex w-full flex-col gap-5">
      <ResurrectionScene
        revived={survival.revived.map((id) => ({ key: `${survival.round}:${id}`, playerId: id, line: (who) => `${who} voltou dos mortos com 1 vida!` }))}
        players={room.players}
        playerId={playerId}
      />
      {strikes[0] && (
        <DaggerStrike key={strikes[0].id} stab={strikes[0].stab} players={room.players} playerId={playerId} onDone={() => setStrikes((queue) => queue.slice(1))} />
      )}
      <header className="flex flex-col items-center gap-1 text-center">
        {duel ? (
          <>
            <p className="font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">X1!</p>
            <p className="text-sm font-semibold text-steel">
              {noun} {survival.duel_round} · {String(survival.next_seconds).replace('.', ',')}s para responder
            </p>
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm font-semibold text-steel">
            {noun} {survival.round}
            <span className={`rounded-full px-2 py-0.5 ${DIFFICULTY_CHIP[survival.difficulty]}`}>{LEVELS[survival.difficulty].title}</span>
            {survival.theme}
          </p>
        )}
      </header>

      {duel ? <DuelCards snapshot={snapshot} playerId={playerId} /> : <SurvivorStrip snapshot={snapshot} playerId={playerId} />}

      {blinded && <div className="flashbang-flash" aria-hidden="true" />}
      {survival.powers && !revealed && (
        <ActivePowerUps
          game={survival}
          players={room.players}
          playerId={playerId}
          concealed={blinded}
          survival
        />
      )}
      {survival.powers && !revealed && answering && !answered && !silenced && <InstantPowerUps game={survival} playerId={playerId} onUse={onUse} />}

      <div className={`h-2 overflow-hidden rounded-full bg-panel ${silenced ? 'invisible' : ''}`}>
        {open && (
          <div
            className={`h-full rounded-full ${remaining < 3000 ? 'bg-red-400' : 'bg-brand'}`}
            style={{ width: `${Math.min(1, remaining / Math.max(1, survival.phase_duration_ms)) * 100}%` }}
          />
        )}
      </div>
      <Magnifier active={hits('magnifier') && !blinded}>
        <ScratchCard active={scratched}>
          <h1 className={`text-[1.4rem] leading-snug font-bold ${choices ? '' : 'text-center'} ${mirrored}`}>{blinded ? '' : text}</h1>
        </ScratchCard>
        <div className={`grid grid-cols-2 gap-3 ${choices ? 'auto-rows-fr' : ''}`}>
          {survival.options.map((option, index) => {
            const hidden = survival.hidden_options.includes(index)
            const state =
              survival.correct_option !== null
                ? index === survival.correct_option
                  ? 'reveal-pop btn-correct text-white'
                  : picksOn(index).length
                    ? 'btn-wrong is-pressed text-white'
                    : 'btn-dark opacity-40'
                : choice === index
                    ? 'btn-dark is-pressed outline-2 outline-brand'
                    : survival.blessing === index && !blinded
                      ? 'btn-dark outline-2 outline-yellow-300 shadow-[0_0_18px_rgba(253,224,71,0.6)]'
                    : hidden
                      ? 'btn-dark opacity-20 line-through'
                      : canAnswer
                        ? 'btn-dark'
                        : 'btn-dark opacity-60'
            return (
              <ScratchCard key={index} active={scratched && !hidden} className="flex">
                <button
                  onClick={() => void pick(index)}
                  disabled={!canAnswer || hidden}
                  className={`btn-3d relative flex w-full items-center rounded-2xl ${
                    choices ? 'btn-sm min-h-14 gap-2 px-3 py-2 text-left text-base leading-tight font-semibold' : 'min-h-24 justify-center px-3 font-display text-2xl tracking-wide'
                  } ${state}`}
                >
                  {choices && <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>}
                  <span className={`${choices ? 'min-w-0 [overflow-wrap:anywhere]' : ''} ${mirrored}`}>
                    {blinded ? '' : scrambled ? scrambleWords(option, survival.round * 7 + index + 1) : option}
                  </span>
                  {survival.peek && !revealed && <PeekBadge count={survival.peek[index]} />}
                  {survival.correct_option !== null && (
                    <span className="absolute -top-2 -right-1.5 flex -space-x-2">
                      {picksOn(index)
                        .slice(0, 5)
                        .map((p) => p && <img key={p.id} src={avatarUrl(p)} alt={p.nickname} className="size-6" />)}
                    </span>
                  )}
                </button>
              </ScratchCard>
            )
          })}
        </div>
      </Magnifier>
      <p className="min-h-7 text-center font-hand text-lg font-medium text-steel">{status}</p>
      {survival.fact && <p className="rounded-xl bg-panel px-4 py-3 text-center text-chalk">{survival.fact}</p>}
      <BannerList items={notes} label="Acontecimentos da rodada" />
      {survival.phase === 'results' && (
        <PowerUpBar
          powers={survival.powers}
          game={survival}
          players={room.players}
          playerId={playerId}
          targetIds={survival.survivors.filter((s) => s.out_round === null).map((s) => s.player_id)}
          hints={SURVIVAL_HINTS}
          lockedNote="No X1 não tem poder."
          emptyNote={me?.out_round !== null ? 'Fantasma: a cada 3 perguntas chega uma sabotagem para jogar nos vivos.' : undefined}
          onArm={onArm}
          onSkip={onSkip}
          onDisarm={onDisarm}
        />
      )}
      {error && <p className="text-center text-red-300">{error}</p>}
    </section>
  )
}

const FLASHBANG_MS = 4000
const TARGETED = new Set(Object.entries(POWERUP_INFO).filter(([, info]) => info.targeted).map(([kind]) => kind))
const cap = (text: string) => text[0].toUpperCase() + text.slice(1)


/** Todos os jogadores com as vidas; quem acabou de perder uma treme, quem caiu fica apagado. */
function SurvivorStrip({ snapshot, playerId }: { snapshot: Snapshot; playerId: string | null }) {
  const { room } = snapshot
  const survival = room.survival!
  const ordered = [...survival.survivors].sort((a, b) => Number(a.out_round !== null) - Number(b.out_round !== null) || (b.out_round ?? 0) - (a.out_round ?? 0))
  return (
    <ul className="flex flex-wrap justify-center gap-2" aria-label="Jogadores">
      {ordered.map((s) => {
        const p = room.players.find((x) => x.id === s.player_id)
        if (!p) return null
        const out = s.out_round !== null
        const pick = survival.picks.find((k) => k.player_id === s.player_id)
        const answered = survival.answered.includes(s.player_id)
        return (
          <li key={s.player_id} className={`flex w-16 flex-col items-center gap-0.5 ${out && !pick ? 'opacity-35 grayscale' : ''} ${pick?.lost_life ? 'reveal-shake' : ''}`}>
            <AnsweredAvatar player={p} done={answered && !pick} waiting={!out && !pick && survival.phase === 'answering'} className="size-11" />
            <span className="w-full truncate text-center text-xs font-semibold">{s.player_id === playerId ? 'Você' : p.nickname}</span>
            {out ? (
              <span className="text-xs font-semibold text-red-300">{pick?.lost_life ? 'Caiu!' : 'Fora'}</span>
            ) : s.lives < 0 ? (
              <span className="text-xs font-semibold text-steel">???</span>
            ) : (
              <Hearts lives={s.lives} max={survival.max_lives} className="size-3.5" />
            )}
          </li>
        )
      })}
    </ul>
  )
}

function DuelCards({ snapshot, playerId }: { snapshot: Snapshot; playerId: string | null }) {
  const { room } = snapshot
  const survival = room.survival!
  const cards = survival.duelists.map((id) => {
    const p = room.players.find((x) => x.id === id)
    if (!p) return null
    const pick = survival.picks.find((k) => k.player_id === id)
    return (
      <div key={id} className="flex flex-col items-center gap-1 rounded-xl bg-panel px-2 py-3">
        <AnsweredAvatar player={p} done={!pick && survival.answered.includes(id)} waiting={!pick && survival.phase === 'duel_answering'} className="size-14" />
        <span className="max-w-full truncate font-semibold">{id === playerId ? 'Você' : p.nickname}</span>
        <span className="h-5 text-sm font-semibold">
          {pick ? (
            pick.correct ? (
              <span className="text-emerald-300">Acertou</span>
            ) : (
              <span className="text-red-300">{pick.option === null ? 'Não respondeu' : 'Errou'}</span>
            )
          ) : (
            ''
          )}
        </span>
      </div>
    )
  })
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
      {cards[0] ?? <span />}
      <span className="font-display text-3xl text-steel">vs</span>
      {cards[1] ?? <span />}
    </div>
  )
}

function outLabel(s: Survivor, survival: SurvivalView) {
  if (s.player_id === survival.winner) return 'Último de pé!'
  return s.out_round === null ? 'Ficou de pé' : `Caiu na ${survival.kind === 'choices' ? 'pergunta' : 'frase'} ${s.out_round}`
}

function SurvivalPodium({ snapshot, playerId, onPlayAgain, onLeave }: { snapshot: Snapshot; playerId: string | null; onPlayAgain: Props['onPlayAgain']; onLeave: () => void }) {
  const { room } = snapshot
  const survival = room.survival!
  const ranked = [...survival.survivors].sort((a, b) => (a.place ?? 99) - (b.place ?? 99))
  const playerOf = (s: Survivor) => room.players.find((p) => p.id === s.player_id)
  const entries = ranked.flatMap((s) => {
    const player = playerOf(s)
    return player ? [{ player, caption: s.player_id === survival.winner ? 'Venceu!' : outLabel(s, survival) }] : []
  })
  return (
    <PlayerPodium
      room={room}
      playerId={playerId}
      onPlayAgain={onPlayAgain}
      onLeave={onLeave}
      ranked={entries}
      worstLine="Primeiro a cair"
      list={
        <ol className="flex flex-col gap-2">
          {ranked.map((s) => {
            const p = playerOf(s)
            if (!p) return null
            return (
              <li key={s.player_id} className={`flex items-center gap-3 rounded-xl bg-panel px-3 py-2 ${s.player_id === playerId ? 'ring-1 ring-brand/60' : ''}`}>
                <span className="w-5 text-center font-display text-lg text-steel">{s.place}</span>
                <img src={avatarUrl(p)} alt="" className="size-9" />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-semibold">{p.nickname}</span>
                  <span className="text-xs text-steel">
                    {outLabel(s, survival)} · {s.correct} {s.correct === 1 ? 'acerto' : 'acertos'}
                  </span>
                </span>
              </li>
            )
          })}
        </ol>
      }
    />
  )
}

