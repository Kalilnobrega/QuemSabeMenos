import { useEffect, useRef, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { POTATO_HINTS, POWERUP_INFO, gainLabel, scrambleWords, type Kind } from '../lib/powerups'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { HotPotatoView, PlayerView, PowerUpUse } from '../types/events'
import { LeaveButton } from './LeaveButton'
import { Magnifier, PowerUpIcon } from './PowerUps'
import { Spotlight } from './Survival'

const LETTERS = ['A', 'B', 'C', 'D']
const HELPS: Kind[] = ['fifty_fifty', 'shield', 'second_chance', 'cold_water', 'reverse', 'free_pass']

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number) => Promise<string | null>
  onUse: (kind: Kind) => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Batata quente: quem está com a batata responde; acertou, passa; o pavio é segredo. */
export function HotPotato({ snapshot, playerId, onAnswer, onUse, onPlayAgain, onLeave }: Props) {
  const potato = snapshot.room.hot_potato!
  if (potato.phase === 'starting') return <PotatoStart snapshot={snapshot} />
  if (potato.phase === 'finished') return <PotatoPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  return <PotatoRound snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} onUse={onUse} />
}

function PotatoIcon({ heat = 0, className }: { heat?: number; className?: string }) {
  // Esquenta do marrom para o vermelho conforme o pavio queima.
  const body = heat > 0.75 ? '#B45309' : heat > 0.45 ? '#A16207' : '#A3753B'
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M38 14c4-6 9-8 13-6" fill="none" stroke="#12141B" strokeWidth="4" strokeLinecap="round" />
      <path d="M38 14c4-6 9-8 13-6" fill="none" stroke="#E5E7EB" strokeWidth="2" strokeLinecap="round" />
      <g className="potato-spark" style={{ transformOrigin: '52px 8px' }}>
        <circle cx="52" cy="8" r="5" fill="#FFC107" />
        <circle cx="52" cy="8" r="2.5" fill="#FFF3C4" />
      </g>
      <ellipse cx="30" cy="38" rx="22" ry="18" fill={body} stroke="#12141B" strokeWidth="3" transform="rotate(-18 30 38)" />
      <circle cx="22" cy="34" r="2" fill="#5B3A16" />
      <circle cx="35" cy="44" r="2.2" fill="#5B3A16" />
      <circle cx="38" cy="31" r="1.6" fill="#5B3A16" />
      <circle cx="25" cy="46" r="1.5" fill="#5B3A16" />
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
  const potato = room.hot_potato!
  const count = Math.ceil(useRemaining(snapshot) / 1000)
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520],
  ])
  useCountdownSounds(count)
  const [low, high] = potato.fuse_range
  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <PotatoIcon className="potato-shake size-20" />
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Batata quente!</h1>
      <ul className="intro-step flex flex-col gap-1 font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        <li>Acertou, a batata passa para o próximo.</li>
        <li>Errou, o pavio perde {potato.penalty_seconds}s.</li>
        <li>{potato.max_wrong_streak} erros seguidos: explode na hora!</li>
        <li className="text-steel">
          O pavio é segredo: dura de {low} a {high}s.
        </li>
      </ul>
      {potato.starting_powerup && (
        <p className="intro-step flex items-center gap-2 rounded-xl bg-panel px-3 py-2 font-semibold" style={{ animationDelay: '0.7s' }}>
          <PowerUpIcon kind={potato.starting_powerup} className="size-6" />
          Seu poder: {POWERUP_INFO[potato.starting_powerup].name}
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
function useHeat(snapshot: Snapshot) {
  const potato = snapshot.room.hot_potato!
  const now = useNow(potato.burning)
  const elapsed = potato.burning ? (now - snapshot.receivedAt) / 1000 : 0
  return Math.min(1, potato.heat + potato.burn_per_second * elapsed)
}

function PotatoRound({ snapshot, playerId, onAnswer, onUse }: { snapshot: Snapshot; playerId: string | null; onAnswer: Props['onAnswer']; onUse: Props['onUse'] }) {
  const { room } = snapshot
  const potato = room.hot_potato!
  const heat = useHeat(snapshot)
  const [choice, setChoice] = useState<{ key: string; option: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const name = (id: string | null | undefined) => (id === playerId ? 'Você' : (room.players.find((p) => p.id === id)?.nickname ?? '?'))
  const mine = potato.holder === playerId
  const questionKey = `${potato.round}-${potato.text}`
  const retry = potato.first_wrong
  const picked = choice?.key === questionKey && choice.option !== retry ? choice.option : null
  const canAnswer = potato.phase === 'asking' && mine && picked === null
  const turn = potato.turn

  // Sabotagens só aparecem para quem está com a batata; quem assiste lê a pergunta limpa.
  const hits = (kind: Kind) => mine && potato.phase === 'asking' && potato.uses.some((u) => u.kind === kind && u.target === playerId)
  const blinded = potato.flashbang && potato.phase === 'asking'
  const mirrored = hits('mirror') ? '-scale-x-100' : ''
  const scrambled = hits('scramble')
  const hitCount = potato.uses.filter((u) => u.target === playerId).length
  useEffect(() => {
    if (hitCount) playSound('powerHit')
  }, [hitCount])
  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])
  useEffect(() => {
    if (potato.revived.length) playSound('resurrection')
  }, [potato.revived.length])

  useEffect(() => {
    if (potato.phase === 'asking' && mine) {
      playSound('answersOpen')
      vibrate(30)
    }
  }, [potato.phase, mine, questionKey])
  useEffect(() => {
    if (potato.phase === 'passing') playSound(turn?.player_id === playerId ? 'correct' : 'skip')
    if (potato.phase === 'wrong') playSound('wrong')
    if (potato.phase === 'exploded') {
      playSound('potatoBoom')
      vibrate([300, 80, 400])
    }
  }, [potato.phase, turn?.player_id, playerId])
  // Chiado: no fim do pavio, quem está com a batata ouve o tique-taque a cada segundo.
  const sizzle = potato.phase === 'asking' && mine && heat > 0.7 ? Math.floor(heat * 40) : 0
  useEffect(() => {
    if (sizzle) playSound('urgentTick')
  }, [sizzle])

  const pick = async (option: number) => {
    if (!canAnswer || potato.hidden_options.includes(option) || option === retry) return
    playSound('select')
    setChoice({ key: questionKey, option })
    const failure = await onAnswer(option)
    if (failure) {
      setChoice(null)
      setError(failure)
    }
  }

  const alive = potato.players.filter((p) => p.out_round === null)
  // Quem acabou de explodir ainda aparece na roda, com o BUM.
  const out = potato.players.filter((p) => p.out_round !== null && !(potato.phase === 'exploded' && p.player_id === potato.exploded))

  let status
  if (potato.phase === 'exploded') status = <span className="text-red-300">{potato.exploded === playerId ? 'Explodiu na sua mão! Você está fora.' : `Explodiu na mão de ${name(potato.exploded)}!`}</span>
  else if (potato.phase === 'passing' && turn?.free_pass) status = <span className="text-emerald-300">{turn.player_id === playerId ? 'Passe livre! Nem precisou responder.' : `${name(turn.player_id)} usou Passe livre!`}</span>
  else if (potato.phase === 'passing') status = <span className="text-emerald-300">{turn?.player_id === playerId ? 'Acertou! Passou a batata.' : `${name(turn?.player_id)} acertou e passou!`}</span>
  else if (potato.phase === 'wrong' && turn?.shielded) status = <span className="text-sky-300">{turn.player_id === playerId ? 'Errou, mas o Escudo segurou!' : `${name(turn.player_id)} errou, mas o Escudo segurou!`}</span>
  else if (potato.phase === 'wrong') status = <span className="text-red-300">{turn?.player_id === playerId ? `Errou! O pavio perdeu ${potato.penalty_seconds}s.` : `${name(turn?.player_id)} errou! −${potato.penalty_seconds}s de pavio.`}</span>
  else if (mine && blinded) status = 'Flashbang! Agora é chutar pela letra.'
  else if (mine && retry !== null) status = 'Errou! Segunda chance: tente de novo.'
  else status = mine ? 'Rápido! Acerta e passa!' : `Vez de ${name(potato.holder)}. Torça ou reze.`

  const showQuestion = potato.phase !== 'exploded' && potato.text
  return (
    <section className="flex w-full flex-col gap-4">
      <header className="flex items-center justify-between text-sm font-semibold text-steel">
        <span>Rodada {potato.round}</span>
        <span>
          {potato.direction === -1 && <span className="mr-2 text-red-300" title="Roda invertida">⟲ invertida</span>}
          {alive.length} na roda
        </span>
      </header>

      <Ring players={room.players} alive={alive.map((p) => p.player_id)} holder={potato.phase === 'exploded' ? potato.exploded : potato.holder} heat={heat} exploded={potato.phase === 'exploded'} shielded={potato.shielded} playerId={playerId} />

      <div className="flex items-center justify-center gap-1.5" aria-label={`${potato.wrong_streak} de ${potato.max_wrong_streak} erros seguidos`}>
        {Array.from({ length: potato.max_wrong_streak }, (_, i) => (
          <span key={i} className={`flex size-6 items-center justify-center rounded-full font-display text-sm ${i < potato.wrong_streak ? 'bg-red-500 text-white' : 'bg-panel text-steel'}`}>
            ✕
          </span>
        ))}
      </div>

      <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>

      {potato.uses.length > 0 && <PotatoUses uses={potato.uses} name={name} playerId={playerId} />}
      {blinded && <div className="flashbang-flash" aria-hidden="true" />}

      {showQuestion && (
        <Magnifier active={hits('magnifier') && !blinded}>
          <h1 className={`text-[1.3rem] leading-snug font-bold ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(potato.text ?? '', potato.round) : potato.text}</h1>
          {/* key: cada pergunta nova monta os botões do zero, sem herdar a cor da anterior. */}
          <div key={questionKey} className="grid auto-rows-fr grid-cols-2 gap-3">
            {potato.options.map((option, index) => {
              const shown = turn && potato.phase !== 'asking'
              const gone = potato.hidden_options.includes(index) || index === retry
              const state = gone && !shown
                ? `btn-dark opacity-25 ${index === retry ? 'line-through' : ''}`
                : shown
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
                  <span className={`min-w-0 [overflow-wrap:anywhere] ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(option, potato.round * 7 + index + 1) : option}</span>
                </button>
              )
            })}
          </div>
        </Magnifier>
      )}

      {potato.powers && <PotatoPowers potato={potato} playerId={playerId} onUse={onUse} />}

      {out.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-steel">
          Fora:
          {out.map((p) => {
            const player = room.players.find((x) => x.id === p.player_id)
            return player ? <img key={p.player_id} src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-7 opacity-40 grayscale" /> : null
          })}
        </div>
      )}
      {error && <p className="text-center text-red-300">{error}</p>}
    </section>
  )
}

/** O que foi usado nesta pergunta: quem jogou o quê em quem. */
function PotatoUses({ uses, name, playerId }: { uses: PowerUpUse[]; name: (id: string | null | undefined) => string; playerId: string | null }) {
  const line = (use: PowerUpUse) => {
    const info = POWERUP_INFO[use.kind]
    const by = name(use.by)
    if (use.target === playerId) return `${by} jogou ${info.name} em você!`
    if (use.target) return `${by} jogou ${info.name} em ${name(use.target)}!`
    const extra: Partial<Record<Kind, string>> = {
      cold_water: ': +10s de pavio',
      fifty_fifty: ': duas erradas saíram',
      shield: ': o próximo erro não conta',
      second_chance: ': errou, tenta de novo',
      reverse: ': a roda inverteu',
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

/** Os poderes na mão: ajudas com a batata na mão, sabotagens em quem está com ela; vale na hora. */
function PotatoPowers({ potato, playerId, onUse }: { potato: HotPotatoView; playerId: string | null; onUse: Props['onUse'] }) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [gift, setGift] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const me = potato.players.find((p) => p.player_id === playerId)
  const ghost = !!me && me.out_round !== null
  const mine = potato.holder === playerId
  const asking = potato.phase === 'asking'
  const threw = potato.uses.some((u) => u.by === playerId && !HELPS.includes(u.kind))
  const myGifts = potato.gifts.filter((g) => g.player_id === playerId)
  const giftKey = myGifts.map((g) => g.gain.kind).join(',')

  useEffect(() => {
    if (!giftKey) return
    playSound('powerArm')
    setGift(myGifts.map((g) => `Você ${gainLabel(g.gain)}`).join(' '))
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setGift(null), 3500)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [giftKey, potato.round])
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const usable = (kind: Kind) => {
    if (busy || !asking || potato.uses.some((u) => u.kind === kind)) return false
    if (HELPS.includes(kind)) return mine && !(kind === 'shield' && potato.shielded.includes(playerId ?? '')) && !(kind === 'second_chance' && potato.first_wrong !== null)
    return !mine && !threw
  }
  const use = async (kind: Kind) => {
    playSound(kind === 'resurrection' ? 'resurrection' : 'powerArm')
    setBusy(true)
    setError(await onUse(kind))
    setBusy(false)
  }

  const hand = potato.powerups
  const note = ghost
    ? 'Fantasma: sabote quem está com a batata. Cada explosão te dá uma sabotagem.'
    : mine
      ? 'Ajudas valem na hora. 3 acertos seguidos dão mais um poder.'
      : 'Sabotagens pegam quem está com a batata, nesta pergunta.'
  return (
    <div className="flex flex-col gap-1.5 rounded-xl bg-panel px-3 py-2.5">
      {gift && <p className="avatar-pop text-sm font-semibold text-brand">{gift}</p>}
      {hand.length === 0 && potato.mythic_powerups.length === 0 ? (
        <p className="text-sm text-steel">{ghost ? 'Sem sabotagens. Espere a próxima explosão.' : 'Sem poderes. Acerte 3 seguidas para ganhar um.'}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {potato.mythic_powerups.map((kind, index) => (
            <button
              key={`mythic-${kind}-${index}`}
              onClick={() => void use(kind)}
              disabled={busy || !ghost}
              title={POTATO_HINTS[kind] ?? POWERUP_INFO[kind].hint}
              className="btn-3d btn-sm mythic mythic-pulse flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold"
            >
              <PowerUpIcon kind={kind} className="size-6" />
              <span className="flex flex-col text-left leading-tight">
                {POWERUP_INFO[kind].name}
                <span className="text-[0.65rem] font-bold tracking-wide uppercase">Voltar para a roda</span>
              </span>
            </button>
          ))}
          {hand.map((kind, index) => {
            const ok = usable(kind)
            return (
              <button
                key={`${kind}-${index}`}
                onClick={() => void use(kind)}
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

/** A roda: os vivos em círculo e a batata voando até quem está com ela. */
function Ring({
  players,
  alive,
  holder,
  heat,
  exploded,
  shielded,
  playerId,
}: {
  players: PlayerView[]
  alive: string[]
  holder: string | null
  heat: number
  exploded: boolean
  shielded: string[]
  playerId: string | null
}) {
  const seats = players.filter((p) => alive.includes(p.id) || p.id === holder)
  const spot = (i: number) => {
    const angle = (i / seats.length) * 2 * Math.PI - Math.PI / 2
    return { left: 50 + 38 * Math.cos(angle), top: 50 + 38 * Math.sin(angle) }
  }
  const at = seats.findIndex((p) => p.id === holder)
  const potatoSpot = at >= 0 ? spot(at) : { left: 50, top: 50 }
  // Treme de 0,6s por balanço (frio) até 0,07s (quase explodindo).
  const shake = `${Math.max(0.07, 0.6 - heat * 0.55).toFixed(2)}s`
  return (
    <div className="relative mx-auto mt-4 aspect-square w-full max-w-72">
      {seats.map((p, i) => {
        const { left, top } = spot(i)
        return (
          <div key={p.id} className="absolute flex w-16 -translate-x-1/2 -translate-y-1/2 flex-col items-center" style={{ left: `${left}%`, top: `${top}%` }}>
            <span className="relative">
              <img src={AVATAR_URLS[p.avatar]} alt="" className={`size-12 ${p.id === holder ? 'drop-shadow-[0_0_10px_rgba(255,120,0,0.9)]' : ''}`} />
              {shielded.includes(p.id) && <PowerUpIcon kind="shield" className="absolute -right-1 -bottom-1 size-5" />}
            </span>
            <span className={`w-full truncate text-center text-xs font-semibold ${p.id === holder ? 'text-brand' : ''}`}>{p.id === playerId ? 'Você' : p.nickname}</span>
          </div>
        )
      })}
      {exploded ? (
        <span className="potato-boom absolute -translate-x-1/2 -translate-y-1/2 font-display text-5xl text-orange-400 [text-shadow:0_4px_0_#7c2d12]" style={{ left: `${potatoSpot.left}%`, top: `${potatoSpot.top - 4}%` }}>
          BUM!
        </span>
      ) : (
        <div className="potato absolute -translate-x-1/2 -translate-y-full" style={{ left: `${potatoSpot.left}%`, top: `${potatoSpot.top - 6}%`, ['--shake' as string]: shake }}>
          <PotatoIcon heat={heat} className="potato-shake size-12" />
        </div>
      )}
    </div>
  )
}

function PotatoPodium({ snapshot, playerId, onPlayAgain, onLeave }: { snapshot: Snapshot; playerId: string | null; onPlayAgain: Props['onPlayAgain']; onLeave: () => void }) {
  const { room } = snapshot
  const potato: HotPotatoView = room.hot_potato!
  const [notice, setNotice] = useState<string | null>(null)
  const ranked = [...potato.players].sort((a, b) => (a.place ?? 99) - (b.place ?? 99))
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
      {winner && <Spotlight title="Mão fria" icon={coroa} player={winner} line={potato.winner === playerId ? 'Você sobreviveu!' : 'Sobreviveu à batata!'} tone="text-brand" winner />}
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
                  {p.player_id === potato.winner ? 'Sobreviveu' : `Queimou na rodada ${p.out_round}`} · {p.correct} {p.correct === 1 ? 'passe' : 'passes'}, {p.wrong}{' '}
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
