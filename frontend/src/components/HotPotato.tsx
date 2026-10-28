import { useEffect, useRef, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { POTATO_HINTS, POWERUP_INFO, gainLabel, scrambleWords, type Kind } from '../lib/powerups'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { HotPotatoView, PotatoView, PowerUpUse } from '../types/events'
import { LeaveButton } from './LeaveButton'
import { Magnifier, PowerUpIcon, ScratchCard } from './PowerUps'
import { Spotlight } from './Survival'

const LETTERS = ['A', 'B', 'C', 'D']
const HELPS: Kind[] = ['fifty_fifty', 'shield', 'second_chance', 'cold_water', 'reverse', 'free_pass', 'thermometer']
const MIN_ALIVE_FOR_DOUBLE = 3
const SCARE_MS = 2200

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number, potato: number) => Promise<string | null>
  onUse: (kind: Kind, potato?: number | null) => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Batata quente: quem está com a batata responde; acertou, passa; o pavio é segredo. */
export function HotPotato({ snapshot, playerId, onAnswer, onUse, onPlayAgain, onLeave }: Props) {
  const game = snapshot.room.hot_potato!
  if (game.phase === 'starting') return <PotatoStart snapshot={snapshot} />
  if (game.phase === 'finished') return <PotatoPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  return <PotatoRound snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} onUse={onUse} />
}

function PotatoIcon({ heat = 0, golden = false, className }: { heat?: number; golden?: boolean; className?: string }) {
  // Esquenta do marrom (ou do dourado, na Batata dupla) para o vermelho conforme o pavio queima.
  const body = golden ? (heat > 0.6 ? '#EAB308' : '#FACC15') : heat > 0.75 ? '#B45309' : heat > 0.45 ? '#A16207' : '#A3753B'
  const spots = golden ? '#A16207' : '#5B3A16'
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M38 14c4-6 9-8 13-6" fill="none" stroke="#12141B" strokeWidth="4" strokeLinecap="round" />
      <path d="M38 14c4-6 9-8 13-6" fill="none" stroke="#E5E7EB" strokeWidth="2" strokeLinecap="round" />
      <g className="potato-spark" style={{ transformOrigin: '52px 8px' }}>
        <circle cx="52" cy="8" r="5" fill="#FFC107" />
        <circle cx="52" cy="8" r="2.5" fill="#FFF3C4" />
      </g>
      <ellipse cx="30" cy="38" rx="22" ry="18" fill={body} stroke="#12141B" strokeWidth="3" transform="rotate(-18 30 38)" />
      <circle cx="22" cy="34" r="2" fill={spots} />
      <circle cx="35" cy="44" r="2.2" fill={spots} />
      <circle cx="38" cy="31" r="1.6" fill={spots} />
      <circle cx="25" cy="46" r="1.5" fill={spots} />
      {golden && <path d="M17 30c3-4 7-6 11-6" fill="none" stroke="#FEF9C3" strokeWidth="2.5" strokeLinecap="round" />}
      {heat > 0.6 && <ellipse cx="30" cy="38" rx="22" ry="18" fill="#EF4444" opacity={(heat - 0.6) * 1.2} transform="rotate(-18 30 38)" />}
    </svg>
  )
}

function useRemaining(snapshot: Snapshot) {
  const now = useNow(true)
  return Math.max(0, snapshot.receivedAt + snapshot.room.hot_potato!.phase_ends_in_ms - now)
}

function PotatoStart({ snapshot }: { snapshot: Snapshot }) {
  const { room } = snapshot
  const game = room.hot_potato!
  const count = Math.ceil(useRemaining(snapshot) / 1000)
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520],
  ])
  useCountdownSounds(count)
  const [low, high] = game.fuse_range
  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <PotatoIcon className="potato-shake size-20" />
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Batata quente!</h1>
      <ul className="intro-step flex flex-col gap-1 font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        <li>Acertou, a batata passa para o próximo.</li>
        <li>Errou, o pavio perde {game.penalty_seconds}s.</li>
        <li>{game.max_wrong_streak} erros seguidos: explode na hora!</li>
        <li className="text-steel">
          O pavio é segredo: dura de {low} a {high}s.
        </li>
      </ul>
      {game.starting_powerup && (
        <p className="intro-step flex items-center gap-2 rounded-xl bg-panel px-3 py-2 font-semibold" style={{ animationDelay: '0.7s' }}>
          <PowerUpIcon kind={game.starting_powerup} className="size-6" />
          Seu poder: {POWERUP_INFO[game.starting_powerup].name}
        </p>
      )}
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

/** Calor de agora: o servidor manda o calor no envio e quanto ele sobe por segundo. */
function useHeat(potato: PotatoView, receivedAt: number) {
  const now = useNow(potato.burning)
  const elapsed = potato.burning ? (now - receivedAt) / 1000 : 0
  return Math.min(1, potato.heat + potato.burn_per_second * elapsed)
}

function potatoName(potato: PotatoView) {
  return potato.golden ? 'Batata dourada' : 'Batata'
}

function PotatoRound({ snapshot, playerId, onAnswer, onUse }: { snapshot: Snapshot; playerId: string | null; onAnswer: Props['onAnswer']; onUse: Props['onUse'] }) {
  const { room } = snapshot
  const game = room.hot_potato!
  const name = (id: string | null | undefined) => (id === playerId ? 'Você' : (room.players.find((p) => p.id === id)?.nickname ?? '?'))
  const exploded = game.phase === 'exploded'
  const mine = game.potatoes.filter((p) => p.holder === playerId)
  // Quem está com batata vê a(s) sua(s) pergunta(s); quem assiste vê a da principal.
  const shown = exploded ? [] : mine.length ? mine : game.potatoes.filter((p) => !p.golden)
  const golden = game.potatoes.find((p) => p.golden)

  useEffect(() => {
    if (!exploded) return
    playSound('potatoBoom')
    vibrate([300, 80, 400])
  }, [exploded])
  useEffect(() => {
    if (game.revived.length) playSound('resurrection')
  }, [game.revived.length])

  // Susto: a batata "explode" na tela de quem está com ela. É de mentira.
  const scares = game.potatoes.flatMap((p) => (p.holder === playerId ? p.uses.filter((u) => u.kind === 'scare').map((u) => `${p.id}-${p.text}-${u.by}`) : []))
  const latestScare = scares.at(-1) ?? null
  // Quem entra no meio de um susto não leva o susto de novo.
  const [doneScare, setDoneScare] = useState(latestScare)
  const scared = latestScare !== null && latestScare !== doneScare
  useEffect(() => {
    if (!scared) return
    playSound('potatoBoom')
    vibrate([300, 80, 400])
    const timer = setTimeout(() => setDoneScare(latestScare), SCARE_MS)
    return () => clearTimeout(timer)
  }, [scared, latestScare])

  const alive = game.players.filter((p) => p.out_round === null)
  // Quem acabou de explodir ainda aparece na roda, com o BUM.
  const out = game.players.filter((p) => p.out_round !== null && !(exploded && p.player_id === game.exploded))

  let status
  if (exploded) {
    const what = game.exploded_golden ? 'A Batata dourada explodiu' : 'Explodiu'
    status = <span className="text-red-300">{game.exploded === playerId ? `${what} na sua mão! Você está fora.` : `${what} na mão de ${name(game.exploded)}!`}</span>
  } else if (!mine.length) {
    status = `Vez de ${name(game.potatoes[0]?.holder)}. Torça ou reze.`
  }

  return (
    <section className="flex w-full flex-col gap-4">
      {scared && <ScareScene />}
      <header className="flex items-center justify-between text-sm font-semibold text-steel">
        <span>Rodada {game.round}</span>
        <span>
          {game.direction === -1 && (
            <span className="mr-2 text-red-300" title="Roda invertida">
              ⟲ invertida
            </span>
          )}
          {alive.length} na roda
        </span>
      </header>

      <Ring snapshot={snapshot} alive={alive.map((p) => p.player_id)} playerId={playerId} />

      {golden && !mine.includes(golden) && !exploded && (
        <p className="flex items-center justify-center gap-2 text-sm font-semibold text-yellow-200">
          <PotatoIcon golden className="size-6" />
          Batata dourada com {name(golden.holder)}
          {golden.excluded && <span className="text-steel">· nunca vai para {name(golden.excluded)}</span>}
        </p>
      )}
      {status && <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>}

      {shown.map((potato) => (
        <QuestionPanel key={potato.id} potato={potato} game={game} receivedAt={snapshot.receivedAt} playerId={playerId} name={name} labeled={game.potatoes.length > 1} onAnswer={onAnswer} />
      ))}

      {game.powers && <PotatoPowers game={game} playerId={playerId} onUse={onUse} />}

      {out.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-steel">
          Fora:
          {out.map((p) => {
            const player = room.players.find((x) => x.id === p.player_id)
            return player ? <img key={p.player_id} src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-7 opacity-40 grayscale" /> : null
          })}
        </div>
      )}
    </section>
  )
}

/** A pergunta de uma batata: quem está com ela responde, quem assiste vê. */
function QuestionPanel({
  potato,
  game,
  receivedAt,
  playerId,
  name,
  labeled,
  onAnswer,
}: {
  potato: PotatoView
  game: HotPotatoView
  receivedAt: number
  playerId: string | null
  name: (id: string | null | undefined) => string
  labeled: boolean
  onAnswer: Props['onAnswer']
}) {
  const [choice, setChoice] = useState<{ key: string; option: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const heat = useHeat(potato, receivedAt)
  const now = useNow(potato.fuse_ms !== null && potato.burning)
  const mine = potato.holder === playerId
  const questionKey = `${game.round}-${potato.text}`
  const retry = potato.first_wrong
  const picked = choice?.key === questionKey && choice.option !== retry ? choice.option : null
  const asking = potato.state === 'asking'
  const canAnswer = asking && mine && picked === null
  const turn = potato.turn

  // Sabotagens só aparecem para quem está com a batata; quem assiste lê a pergunta limpa.
  const hits = (kind: Kind) => mine && asking && potato.uses.some((u) => u.kind === kind && u.target === playerId)
  const blinded = potato.flashbang && asking
  const mirrored = hits('mirror') ? '-scale-x-100' : ''
  const scrambled = hits('scramble')
  // A Raspadinha chega no meio da pergunta: a chave remonta a cobertura na hora.
  const scratched = hits('scratch') && !blinded
  const hitCount = potato.uses.filter((u) => u.target === playerId && u.kind !== 'scare').length
  useEffect(() => {
    if (hitCount) playSound('powerHit')
  }, [hitCount])
  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])
  useEffect(() => {
    if (asking && mine) {
      playSound('answersOpen')
      vibrate(30)
    }
  }, [asking, mine, questionKey])
  useEffect(() => {
    if (potato.state === 'passing') playSound(turn?.player_id === playerId ? 'correct' : 'skip')
    if (potato.state === 'again' && turn?.player_id === playerId) playSound('correct')
    if (potato.state === 'wrong') playSound('wrong')
  }, [potato.state, turn?.player_id, playerId])
  // Chiado: no fim do pavio, quem está com a batata ouve o tique-taque a cada segundo.
  const sizzle = asking && mine && heat > 0.7 ? Math.floor(heat * 40) : 0
  useEffect(() => {
    if (sizzle) playSound('urgentTick')
  }, [sizzle])

  const pick = async (option: number) => {
    if (!canAnswer || potato.hidden_options.includes(option) || option === retry) return
    playSound('select')
    setChoice({ key: questionKey, option })
    const failure = await onAnswer(option, potato.id)
    if (failure) {
      setChoice(null)
      setError(failure)
    }
  }

  let status
  if (potato.state === 'passing' && turn?.free_pass) status = <span className="text-emerald-300">{turn.player_id === playerId ? 'Passe livre! Nem precisou responder.' : `${name(turn.player_id)} usou Passe livre!`}</span>
  else if (potato.state === 'passing') status = <span className="text-emerald-300">{turn?.player_id === playerId ? 'Acertou! Passou a batata.' : `${name(turn?.player_id)} acertou e passou!`}</span>
  else if (potato.state === 'again') status = <span className="text-emerald-300">{turn?.player_id === playerId ? 'Acertou! Bomba dupla: mais uma para passar.' : `${name(turn?.player_id)} acertou, mas a Bomba dupla pede mais uma!`}</span>
  else if (potato.state === 'wrong' && turn?.shielded) status = <span className="text-sky-300">{turn.player_id === playerId ? 'Errou, mas o Escudo segurou!' : `${name(turn.player_id)} errou, mas o Escudo segurou!`}</span>
  else if (potato.state === 'wrong') status = <span className="text-red-300">{turn?.player_id === playerId ? `Errou! O pavio perdeu ${game.penalty_seconds}s.` : `${name(turn?.player_id)} errou! −${game.penalty_seconds}s de pavio.`}</span>
  else if (mine && blinded) status = 'Flashbang! Agora é chutar pela letra.'
  else if (mine && retry !== null) status = 'Errou! Segunda chance: tente de novo.'
  else if (mine) status = 'Rápido! Acerta e passa!'

  const fuseLeft = potato.fuse_ms === null ? null : Math.max(0, potato.fuse_ms - (potato.burning ? now - receivedAt : 0))

  return (
    <div className={`flex flex-col gap-3 ${labeled ? `rounded-2xl p-3 ${potato.golden ? 'bg-yellow-300/10 ring-1 ring-yellow-300/40' : 'bg-panel/60'}` : ''}`}>
      {labeled && (
        <p className={`flex items-center gap-2 font-display text-lg ${potato.golden ? 'text-yellow-200' : 'text-brand'}`}>
          <PotatoIcon heat={heat} golden={potato.golden} className="size-7" />
          {potatoName(potato)}
          {!mine && <span className="font-sans text-sm text-steel">com {name(potato.holder)}</span>}
        </p>
      )}
      <div className="flex items-center justify-center gap-3">
        <span className="flex items-center gap-1.5" aria-label={`${potato.wrong_streak} de ${game.max_wrong_streak} erros seguidos`}>
          {Array.from({ length: game.max_wrong_streak }, (_, i) => (
            <span key={i} className={`flex size-6 items-center justify-center rounded-full font-display text-sm ${i < potato.wrong_streak ? 'bg-red-500 text-white' : 'bg-panel text-steel'}`}>
              ✕
            </span>
          ))}
        </span>
        {potato.need_right > 1 && (
          <span className="flex items-center gap-1 rounded-full bg-orange-500/20 px-2 py-0.5 text-sm font-semibold text-orange-200">
            <PowerUpIcon kind="double_bomb" className="size-5" />
            mais {potato.need_right} para passar
          </span>
        )}
        {fuseLeft !== null && (
          <span className="flex items-center gap-1 rounded-full bg-sky-400/20 px-2 py-0.5 font-display text-lg text-sky-100" title="Termômetro: o pavio que falta">
            <PowerUpIcon kind="thermometer" className="size-5" />
            {(fuseLeft / 1000).toFixed(1).replace('.', ',')}s
          </span>
        )}
      </div>
      {status && <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>}
      {potato.uses.length > 0 && <PotatoUses uses={potato.uses} name={name} playerId={playerId} />}
      {blinded && <div className="flashbang-flash" aria-hidden="true" />}
      {potato.text && (
        <Magnifier active={hits('magnifier') && !blinded}>
          <ScratchCard key={`${questionKey}-${scratched}`} active={scratched}>
            <h1 className={`text-[1.3rem] leading-snug font-bold ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(potato.text, game.round) : potato.text}</h1>
          </ScratchCard>
          {/* key: cada pergunta nova monta os botões do zero, sem herdar a cor da anterior. */}
          <ScratchCard key={`${questionKey}-${scratched}-options`} active={scratched}>
            <div key={questionKey} className="grid auto-rows-fr grid-cols-2 gap-3">
              {potato.options.map((option, index) => {
                const reveal = turn && !asking
                const gone = potato.hidden_options.includes(index) || index === retry
                const state =
                  gone && !reveal
                    ? `btn-dark opacity-25 ${index === retry ? 'line-through' : ''}`
                    : reveal
                      ? index === turn.correct_option
                        ? 'btn-correct text-white'
                        : index === turn.option
                          ? 'btn-wrong is-pressed text-white'
                          : 'btn-dark opacity-40'
                      : picked === index
                        ? 'btn-dark is-pressed outline-2 outline-brand'
                        : canAnswer
                          ? 'btn-dark'
                          : 'btn-dark opacity-60'
                return (
                  <button
                    key={index}
                    onClick={() => void pick(index)}
                    disabled={!canAnswer || gone}
                    className={`btn-3d btn-sm flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${state}`}
                  >
                    <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
                    <span className={`min-w-0 [overflow-wrap:anywhere] ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(option, game.round * 7 + index + 1) : option}</span>
                  </button>
                )
              })}
            </div>
          </ScratchCard>
        </Magnifier>
      )}
      {error && <p className="text-center text-red-300">{error}</p>}
    </div>
  )
}

/** Susto: a explosão de mentira na tela de quem está com a batata. */
function ScareScene() {
  return (
    <div className="scare-scene" role="alert">
      <span className="potato-boom font-display text-8xl text-orange-400 [text-shadow:0_6px_0_#7c2d12]">BUM!</span>
      <p className="scare-joke font-display text-3xl text-chalk">Brincadeira! Foi só um susto.</p>
    </div>
  )
}

/** O que foi usado nesta pergunta: quem jogou o quê em quem. */
function PotatoUses({ uses, name, playerId }: { uses: PowerUpUse[]; name: (id: string | null | undefined) => string; playerId: string | null }) {
  const line = (use: PowerUpUse) => {
    const info = POWERUP_INFO[use.kind]
    const by = name(use.by)
    if (use.kind === 'scare') return use.target === playerId ? `${by} te deu um susto!` : `${by} deu um susto em ${name(use.target)}!`
    if (use.target === playerId) return `${by} jogou ${info.name} em você!`
    if (use.target) return `${by} jogou ${info.name} em ${name(use.target)}!`
    const extra: Partial<Record<Kind, string>> = {
      cold_water: ': +10s de pavio',
      fifty_fifty: ': duas erradas saíram',
      shield: ': o próximo erro não conta',
      second_chance: ': errou, tenta de novo',
      reverse: ': a roda inverteu',
      thermometer: ': está vendo o pavio',
    }
    return `${by} usou ${info.name}${extra[use.kind] ?? ''}!`
  }
  return (
    <ul className="flex flex-col gap-1" aria-label="Poderes nesta pergunta">
      {uses.map((use) => (
        <li key={`${use.by}-${use.kind}`} className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1 text-sm font-semibold ${POWERUP_INFO[use.kind].tone}`}>
          <PowerUpIcon kind={use.kind} className="size-5 shrink-0" />
          <span className="min-w-0">{line(use)}</span>
        </li>
      ))}
    </ul>
  )
}

/** Os poderes na mão: ajudas com a batata na mão, sabotagens em quem está com ela; vale na hora.
 *  Com duas batatas na roda, escolhe-se em qual. */
function PotatoPowers({ game, playerId, onUse }: { game: HotPotatoView; playerId: string | null; onUse: Props['onUse'] }) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [gift, setGift] = useState<string | null>(null)
  const [choosing, setChoosing] = useState<{ kind: Kind; potatoes: PotatoView[] } | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const me = game.players.find((p) => p.player_id === playerId)
  const ghost = !!me && me.out_round !== null
  const alive = game.players.filter((p) => p.out_round === null).length
  const playing = game.phase === 'playing'
  const myGifts = game.gifts.filter((g) => g.player_id === playerId)
  const giftKey = myGifts.map((g) => g.gain.kind).join(',')

  useEffect(() => {
    if (!giftKey) return
    playSound('powerArm')
    setGift(myGifts.map((g) => `Você ${gainLabel(g.gain)}`).join(' '))
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setGift(null), 3500)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [giftKey, game.round])
  useEffect(() => () => window.clearTimeout(timer.current), [])

  // As batatas em que cada poder pode valer agora.
  const targets = (kind: Kind) => {
    if (busy || !playing) return []
    const open = game.potatoes.filter((p) => p.state === 'asking' && !p.uses.some((u) => u.kind === kind))
    if (HELPS.includes(kind)) {
      return open.filter(
        (p) =>
          p.holder === playerId &&
          !(kind === 'shield' && game.shielded.includes(playerId ?? '')) &&
          !(kind === 'second_chance' && p.first_wrong !== null) &&
          !(kind === 'thermometer' && p.fuse_ms !== null),
      )
    }
    return open.filter((p) => p.holder !== playerId && !p.uses.some((u) => u.by === playerId && !HELPS.includes(u.kind)))
  }
  const fire = async (kind: Kind, potato: number | null = null) => {
    playSound(kind === 'resurrection' ? 'resurrection' : 'powerArm')
    setChoosing(null)
    setBusy(true)
    setError(await onUse(kind, potato))
    setBusy(false)
  }
  const tap = (kind: Kind) => {
    const options = targets(kind)
    if (options.length > 1) return setChoosing({ kind, potatoes: options })
    void fire(kind, options[0]?.id ?? null)
  }
  const mythicReady = (kind: Kind) => {
    if (busy || !playing) return false
    if (kind === 'resurrection') return ghost
    return !ghost && alive >= MIN_ALIVE_FOR_DOUBLE && !game.potatoes.some((p) => p.golden)
  }

  const hand = game.powerups
  const mineNow = game.potatoes.some((p) => p.holder === playerId)
  const note = ghost
    ? 'Fantasma: sabote quem está com a batata. Cada explosão te dá uma sabotagem.'
    : mineNow
      ? 'Ajudas valem na hora. 3 acertos seguidos dão mais um poder.'
      : 'Sabotagens pegam quem está com a batata, nesta pergunta.'
  return (
    <div className="flex flex-col gap-1.5 rounded-xl bg-panel px-3 py-2.5">
      {gift && <p className="avatar-pop text-sm font-semibold text-brand">{gift}</p>}
      {choosing ? (
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <PowerUpIcon kind={choosing.kind} className="size-6" />
            {POWERUP_INFO[choosing.kind].name}: em qual batata?
          </p>
          <div className="flex gap-2">
            {choosing.potatoes.map((p) => (
              <button
                key={p.id}
                onClick={() => void fire(choosing.kind, p.id)}
                className={`btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${p.golden ? 'text-yellow-200' : ''}`}
              >
                <PotatoIcon golden={p.golden} className="size-6" />
                {potatoName(p)}
              </button>
            ))}
            <button onClick={() => setChoosing(null)} className="btn-3d btn-sm btn-dark rounded-xl px-3 py-1.5 font-semibold text-steel">
              Cancelar
            </button>
          </div>
        </div>
      ) : hand.length === 0 && game.mythic_powerups.length === 0 ? (
        <p className="text-sm text-steel">{ghost ? 'Sem sabotagens. Espere a próxima explosão.' : 'Sem poderes. Acerte 3 seguidas para ganhar um.'}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {game.mythic_powerups.map((kind, index) => (
            <button
              key={`mythic-${kind}-${index}`}
              onClick={() => void fire(kind)}
              disabled={!mythicReady(kind)}
              title={POTATO_HINTS[kind] ?? POWERUP_INFO[kind].hint}
              className={`btn-3d btn-sm mythic mythic-pulse flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${mythicReady(kind) ? '' : 'opacity-50'}`}
            >
              <PowerUpIcon kind={kind} className="size-6" />
              <span className="flex flex-col text-left leading-tight">
                {POWERUP_INFO[kind].name}
                <span className="text-[0.65rem] font-bold tracking-wide uppercase">{kind === 'resurrection' ? 'Voltar para a roda' : 'Colocar na roda'}</span>
              </span>
            </button>
          ))}
          {hand.map((kind, index) => {
            const ok = targets(kind).length > 0
            return (
              <button
                key={`${kind}-${index}`}
                onClick={() => tap(kind)}
                disabled={!ok}
                title={POTATO_HINTS[kind] ?? POWERUP_INFO[kind].hint}
                className={`btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${ok ? '' : 'opacity-40'}`}
              >
                <PowerUpIcon kind={kind} className="size-6" />
                <span className="flex flex-col text-left leading-tight">
                  {POWERUP_INFO[kind].name}
                  <span className="text-[0.65rem] font-normal text-steel">{HELPS.includes(kind) ? 'ajuda' : 'sabotagem'}</span>
                </span>
              </button>
            )
          })}
        </div>
      )}
      <p className="text-xs text-steel">{note}</p>
      {error && <p className="text-sm text-red-300">{error}</p>}
    </div>
  )
}

/** A roda: os vivos em círculo e as batatas voando até quem está com elas. */
function Ring({ snapshot, alive, playerId }: { snapshot: Snapshot; alive: string[]; playerId: string | null }) {
  const { room, receivedAt } = snapshot
  const game = room.hot_potato!
  const exploded = game.phase === 'exploded'
  const holders = game.potatoes.map((p) => p.holder)
  const seats = room.players.filter((p) => alive.includes(p.id) || holders.includes(p.id) || p.id === game.exploded)
  const spot = (id: string | null | undefined) => {
    const i = seats.findIndex((p) => p.id === id)
    if (i < 0) return { left: 50, top: 50 }
    const angle = (i / seats.length) * 2 * Math.PI - Math.PI / 2
    return { left: 50 + 38 * Math.cos(angle), top: 50 + 38 * Math.sin(angle) }
  }
  const boom = spot(game.exploded)
  return (
    <div className="relative mx-auto mt-4 aspect-square w-full max-w-72">
      {seats.map((p) => {
        const { left, top } = spot(p.id)
        const holding = holders.includes(p.id)
        return (
          <div key={p.id} className="absolute flex w-16 -translate-x-1/2 -translate-y-1/2 flex-col items-center" style={{ left: `${left}%`, top: `${top}%` }}>
            <span className="relative">
              <img src={AVATAR_URLS[p.avatar]} alt="" className={`size-12 ${holding ? 'drop-shadow-[0_0_10px_rgba(255,120,0,0.9)]' : ''}`} />
              {game.shielded.includes(p.id) && <PowerUpIcon kind="shield" className="absolute -right-1 -bottom-1 size-5" />}
            </span>
            <span className={`w-full truncate text-center text-xs font-semibold ${holding ? 'text-brand' : ''}`}>{p.id === playerId ? 'Você' : p.nickname}</span>
          </div>
        )
      })}
      {exploded && (
        <span
          className={`potato-boom absolute -translate-x-1/2 -translate-y-1/2 font-display text-5xl ${game.exploded_golden ? 'text-yellow-300' : 'text-orange-400'} [text-shadow:0_4px_0_#7c2d12]`}
          style={{ left: `${boom.left}%`, top: `${boom.top - 4}%` }}
        >
          BUM!
        </span>
      )}
      {game.potatoes
        .filter((p) => !(exploded && p.holder === game.exploded && (p.golden === game.exploded_golden)))
        .map((potato) => (
          <FlyingPotato key={potato.id} potato={potato} receivedAt={receivedAt} spot={spot(potato.holder)} paired={game.potatoes.filter((p) => p.holder === potato.holder).length > 1} />
        ))}
    </div>
  )
}

function FlyingPotato({ potato, receivedAt, spot, paired }: { potato: PotatoView; receivedAt: number; spot: { left: number; top: number }; paired: boolean }) {
  const heat = useHeat(potato, receivedAt)
  // Treme de 0,6s por balanço (frio) até 0,07s (quase explodindo).
  const shake = `${Math.max(0.07, 0.6 - heat * 0.55).toFixed(2)}s`
  // Com as duas na mesma mão, a dourada fica um pouco para o lado.
  const shift = paired ? (potato.golden ? 7 : -7) : 0
  return (
    <div className="potato absolute -translate-x-1/2 -translate-y-full" style={{ left: `${spot.left + shift}%`, top: `${spot.top - 6}%`, ['--shake' as string]: shake }}>
      <PotatoIcon heat={heat} golden={potato.golden} className="potato-shake size-12" />
    </div>
  )
}

function PotatoPodium({ snapshot, playerId, onPlayAgain, onLeave }: { snapshot: Snapshot; playerId: string | null; onPlayAgain: Props['onPlayAgain']; onLeave: () => void }) {
  const { room } = snapshot
  const game: HotPotatoView = room.hot_potato!
  const [notice, setNotice] = useState<string | null>(null)
  const ranked = [...game.players].sort((a, b) => (a.place ?? 99) - (b.place ?? 99))
  const playerOf = (id: string) => room.players.find((p) => p.id === id)
  const winner = ranked[0] && playerOf(ranked[0].player_id)
  const first = ranked.length > 1 ? playerOf(ranked[ranked.length - 1].player_id) : undefined
  const isHost = room.host_id === playerId
  useSoundsOnMount([
    ['podiumWinner', 300],
    ['podiumLoser', 3200],
  ])
  return (
    <section className="flex w-full flex-col gap-6">
      <h1 className="text-center font-display text-5xl tracking-wide text-brand">Fim de jogo!</h1>
      {winner && <Spotlight title="Mão fria" icon={coroa} player={winner} line={game.winner === playerId ? 'Você sobreviveu!' : 'Sobreviveu à batata!'} tone="text-brand" winner />}
      {first && <Spotlight title="Quem sabe menos" icon={haha} player={first} line="Primeiro a queimar" tone="text-red-300" />}
      <ol className="flex flex-col gap-2">
        {ranked.map((p) => {
          const player = playerOf(p.player_id)
          if (!player) return null
          return (
            <li key={p.player_id} className={`flex items-center gap-3 rounded-xl bg-panel px-3 py-2 ${p.player_id === playerId ? 'outline-2 outline-brand' : ''}`}>
              <span className="w-8 text-center font-display text-2xl text-steel">{p.place}º</span>
              <img src={AVATAR_URLS[player.avatar]} alt="" className="size-10" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-semibold">{player.nickname}</span>
                <span className="text-xs text-steel">
                  {p.player_id === game.winner ? 'Sobreviveu' : `Queimou na rodada ${p.out_round}`} · {p.correct} {p.correct === 1 ? 'passe' : 'passes'}, {p.wrong}{' '}
                  {p.wrong === 1 ? 'erro' : 'erros'}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
      {notice && <p className="text-center text-steel">{notice}</p>}
      {isHost ? (
        <button onClick={async () => setNotice(await onPlayAgain())} className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink">
          Jogar de novo
        </button>
      ) : (
        <p className="text-center font-hand text-lg font-medium text-steel">Esperando o anfitrião decidir se tem revanche…</p>
      )}
      <LeaveButton onLeave={onLeave} />
    </section>
  )
}
