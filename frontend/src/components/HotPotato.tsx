import { useEffect, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { playSound } from '../lib/sounds'
import type { Snapshot } from '../lib/useRoom'
import type { HotPotatoView, PlayerView } from '../types/events'
import { LeaveButton } from './LeaveButton'
import { Spotlight } from './Survival'

const LETTERS = ['A', 'B', 'C', 'D']

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number) => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Batata quente: quem está com a batata responde; acertou, passa; o pavio é segredo. */
export function HotPotato({ snapshot, playerId, onAnswer, onPlayAgain, onLeave }: Props) {
  const potato = snapshot.room.hot_potato!
  if (potato.phase === 'starting') return <PotatoStart snapshot={snapshot} />
  if (potato.phase === 'finished') return <PotatoPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  return <PotatoRound snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} />
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

function PotatoRound({ snapshot, playerId, onAnswer }: { snapshot: Snapshot; playerId: string | null; onAnswer: Props['onAnswer'] }) {
  const { room } = snapshot
  const potato = room.hot_potato!
  const heat = useHeat(snapshot)
  const [choice, setChoice] = useState<{ key: string; option: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const name = (id: string | null | undefined) => (id === playerId ? 'Você' : (room.players.find((p) => p.id === id)?.nickname ?? '?'))
  const mine = potato.holder === playerId
  const questionKey = `${potato.round}-${potato.text}`
  const picked = choice?.key === questionKey ? choice.option : null
  const canAnswer = potato.phase === 'asking' && mine && picked === null
  const turn = potato.turn

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
      playSound('flashbang')
      vibrate([300, 80, 400])
    }
  }, [potato.phase, turn?.player_id, playerId])
  // Chiado: no fim do pavio, quem está com a batata ouve o tique-taque a cada segundo.
  const sizzle = potato.phase === 'asking' && mine && heat > 0.7 ? Math.floor(heat * 40) : 0
  useEffect(() => {
    if (sizzle) playSound('urgentTick')
  }, [sizzle])

  const pick = async (option: number) => {
    if (!canAnswer) return
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
  else if (potato.phase === 'passing') status = <span className="text-emerald-300">{turn?.player_id === playerId ? 'Acertou! Passou a batata.' : `${name(turn?.player_id)} acertou e passou!`}</span>
  else if (potato.phase === 'wrong') status = <span className="text-red-300">{turn?.player_id === playerId ? `Errou! O pavio perdeu ${potato.penalty_seconds}s.` : `${name(turn?.player_id)} errou! −${potato.penalty_seconds}s de pavio.`}</span>
  else status = mine ? 'Rápido! Acerta e passa!' : `Vez de ${name(potato.holder)}. Torça ou reze.`

  const showQuestion = potato.phase !== 'exploded' && potato.text
  return (
    <section className="flex w-full flex-col gap-4">
      <header className="flex items-center justify-between text-sm font-semibold text-steel">
        <span>Rodada {potato.round}</span>
        <span>{alive.length} na roda</span>
      </header>

      <Ring players={room.players} alive={alive.map((p) => p.player_id)} holder={potato.phase === 'exploded' ? potato.exploded : potato.holder} heat={heat} exploded={potato.phase === 'exploded'} playerId={playerId} />

      <div className="flex items-center justify-center gap-1.5" aria-label={`${potato.wrong_streak} de ${potato.max_wrong_streak} erros seguidos`}>
        {Array.from({ length: potato.max_wrong_streak }, (_, i) => (
          <span key={i} className={`flex size-6 items-center justify-center rounded-full font-display text-sm ${i < potato.wrong_streak ? 'bg-red-500 text-white' : 'bg-panel text-steel'}`}>
            ✕
          </span>
        ))}
      </div>

      <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>

      {showQuestion && (
        <>
          <h1 className="text-[1.3rem] leading-snug font-bold">{potato.text}</h1>
          {/* key: cada pergunta nova monta os botões do zero, sem herdar a cor da anterior. */}
          <div key={questionKey} className="grid auto-rows-fr grid-cols-2 gap-3">
            {potato.options.map((option, index) => {
              const shown = turn && potato.phase !== 'asking'
              const state = shown
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
                  disabled={!canAnswer}
                  className={`btn-3d btn-sm flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${state}`}
                >
                  <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
                  <span className="min-w-0 [overflow-wrap:anywhere]">{option}</span>
                </button>
              )
            })}
          </div>
        </>
      )}

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

/** A roda: os vivos em círculo e a batata voando até quem está com ela. */
function Ring({ players, alive, holder, heat, exploded, playerId }: { players: PlayerView[]; alive: string[]; holder: string | null; heat: number; exploded: boolean; playerId: string | null }) {
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
            <img src={AVATAR_URLS[p.avatar]} alt="" className={`size-12 ${p.id === holder ? 'drop-shadow-[0_0_10px_rgba(255,120,0,0.9)]' : ''}`} />
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
