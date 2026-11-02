/**
 * Telas que todos os modos compartilham: início da partida, troca de nível, final impossível,
 * fim de jogo (pódio) e o botão Pular da revelação. Cada modo só passa o que é dele (as regras
 * da abertura, a linha embaixo de cada um no pódio), e a animação e os sons ficam iguais em todos.
 */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { avatarUrl } from '../lib/avatars'
import { reducedMotion, useCountdownSounds, useNow, useSoundsOnMount } from '../lib/effects'
import { POWERUP_INFO, type Kind } from '../lib/powerups'
import { playSound, type SoundId } from '../lib/sounds'
import type { PlayerView, RoomState } from '../types/events'
import { Confetti, Flame, FlameIcon } from './Game'
import { LeaveButton } from './LeaveButton'
import { PowerUpIcon } from './PowerUps'

/** Segundos que faltam para a fase acabar, contando do momento em que o estado chegou. */
function useCount(receivedAt: number, endsInMs: number) {
  const now = useNow(true)
  return Math.ceil(Math.max(0, receivedAt + endsInMs - now) / 1000)
}

function Countdown({ count }: { count: number }) {
  return (
    <div className="flex h-20 items-center" aria-live="polite">
      {count <= 3 && count > 0 && (
        <span key={count} className="intro-count font-display text-7xl text-chalk">
          {count}
        </span>
      )}
    </div>
  )
}

function AvatarRow({ players }: { players: PlayerView[] }) {
  return (
    <ul className="flex max-w-xs flex-wrap justify-center gap-2" aria-label="Jogadores">
      {players.map((player, index) => (
        <li key={player.id} className="avatar-pop" style={{ animationDelay: `${0.8 + index * 0.08}s` }}>
          <img src={avatarUrl(player)} alt={player.nickname} title={player.nickname} className="size-12" />
        </li>
      ))}
    </ul>
  )
}

interface StartScreenProps {
  room: RoomState
  receivedAt: number
  endsInMs: number
  /** O nome do modo, em cima do título (o Clássico mostra "A partida vai começar"). */
  eyebrow: string
  title?: string
  /** Um desenho acima do título (a batata, por exemplo). */
  icon?: ReactNode
  /** As regras ou o resumo da partida, em linhas curtas. */
  rules: ReactNode[]
  /** O poder sorteado no começo. */
  power?: { kind: Kind; label?: string } | null
  /** No lugar da fileira de avatares (o Times mostra o seu time). */
  players?: ReactNode
  footer?: ReactNode
}

/** "Prepare-se!": o título bate na tela, as regras sobem, os avatares pulam e a contagem fecha. */
export function StartScreen({ room, receivedAt, endsInMs, eyebrow, title = 'Prepare-se!', icon, rules, power, players, footer }: StartScreenProps) {
  const count = useCount(receivedAt, endsInMs)
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520], // a batida cai aos 0,15 s do som, quando o título encosta na tela
  ])
  useCountdownSounds(count)

  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      {icon}
      <p className="intro-step text-sm font-semibold tracking-[0.3em] text-steel uppercase">{eyebrow}</p>
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">{title}</h1>
      <ul className="intro-step flex max-w-xs flex-col gap-1 font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.6s' }}>
        {rules.map((rule, index) => (
          <li key={index} className="flex flex-wrap items-center justify-center gap-x-2">
            {rule}
          </li>
        ))}
      </ul>
      {players ?? <AvatarRow players={room.players} />}
      {power && (
        <p
          className={`intro-step flex items-center gap-2 rounded-xl px-4 py-2 font-semibold ${POWERUP_INFO[power.kind].tone}`}
          style={{ animationDelay: '1.2s' }}
        >
          <PowerUpIcon kind={power.kind} className="size-6" />
          {power.label ?? 'Seu poder'}: {POWERUP_INFO[power.kind].name}
        </p>
      )}
      <Countdown count={count} />
      {footer}
    </section>
  )
}

const LEVEL_TRACK: { key: string; label: ReactNode }[] = [
  { key: 'easy', label: 'Fácil' },
  { key: 'medium', label: 'Média' },
  { key: 'hard', label: 'Difícil' },
  { key: 'impossible', label: <FlameIcon className="size-3.5" /> },
]

const LEVEL_INTRO: Record<string, { title: string; color: string; marker: string; shadow: string; line: string }> = {
  easy: {
    title: 'Fácil',
    color: 'text-emerald-300',
    marker: 'bg-emerald-400',
    shadow: '#065f46',
    line: 'Para esquentar.',
  },
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
  impossible: {
    title: 'Impossível',
    color: 'text-orange-300',
    marker: 'bg-orange-400',
    shadow: '#7c2d12',
    line: 'Tudo pode virar.',
  },
}

/** Troca de nível: o destaque pula na trilha e o nome do nível bate na tela. `line` troca a frase
 * de baixo quando a regra do modo é outra (Último de pé, Chutômetro). */
export function LevelIntro({ difficulty, line }: { difficulty: string; line?: ReactNode }) {
  const info = LEVEL_INTRO[difficulty] ?? LEVEL_INTRO.medium
  const current = LEVEL_TRACK.findIndex((level) => level.key === difficulty)
  const trackRef = useRef<HTMLOListElement>(null)
  const markerRef = useRef<HTMLSpanElement>(null)
  useSoundsOnMount([
    ['levelHop', 450],
    ['levelUp', 1050],
  ])

  useLayoutEffect(() => {
    const track = trackRef.current
    const marker = markerRef.current
    if (!track || !marker || current < 0) return
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
        {line ?? info.line}
      </p>
    </section>
  )
}

/** A entrada da pergunta impossível: chama, carimbo e o que está em jogo. */
export function ImpossibleIntro({ receivedAt, endsInMs, line, children }: { receivedAt: number; endsInMs: number; line: ReactNode; children?: ReactNode }) {
  const count = useCount(receivedAt, endsInMs)
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
      <p className="intro-step intro-step-late max-w-xs font-hand text-lg font-medium text-chalk">{line}</p>
      {children}
      <Countdown count={count} />
    </section>
  )
}

interface EndScreenProps {
  room: RoomState
  playerId: string | null
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
  /** Falso enquanto o pódio ainda está aparecendo: no lugar dos botões fica o Pular. */
  done?: boolean
  onSkipIntro?: () => void
  children: ReactNode
}

/** A moldura do fim de jogo: título, o pódio do modo e os botões de revanche e sair. */
export function EndScreen({ room, playerId, onPlayAgain, onLeave, done = true, onSkipIntro, children }: EndScreenProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const isHost = room.host_id === playerId
  return (
    <section className="flex w-full flex-col gap-6">
      <h1 className="text-center font-display text-5xl tracking-wide text-brand">Fim de jogo!</h1>
      {children}
      {done ? (
        <>
          {notice && <p className="text-center text-steel">{notice}</p>}
          {isHost ? (
            <button
              onClick={async () => {
                playSound('click')
                setNotice(await onPlayAgain())
              }}
              className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink"
            >
              Jogar de novo
            </button>
          ) : (
            <p className="text-center font-hand text-lg font-medium text-steel">Esperando o anfitrião decidir se tem revanche…</p>
          )}
          <LeaveButton onLeave={onLeave} />
        </>
      ) : (
        <button onClick={onSkipIntro} className="mx-auto font-semibold text-steel underline-offset-4 hover:underline">
          Pular
        </button>
      )}
    </section>
  )
}

/** Um jogador no pódio: `caption` vai embaixo do nome (o QI, "Sobreviveu", "Caiu na rodada 5"). */
export interface PodiumEntry {
  player: PlayerView
  caption: ReactNode
}

// Momentos da revelação do pódio, em ms: 3º, 2º, 1º (com fanfarra e confete), o último e, por fim, o resto da tela.
const PODIUM_STEPS = [900, 2300, 3800, 6300, 8000]

const PODIUM_PLACES = [
  { place: 1, label: '1º', step: 'h-24 bg-brand text-ink', order: 'order-2' },
  { place: 2, label: '2º', step: 'h-16 bg-slate-300 text-ink', order: 'order-1' },
  { place: 3, label: '3º', step: 'h-10 bg-amber-700 text-chalk', order: 'order-3' },
]

interface PlayerPodiumProps extends Omit<EndScreenProps, 'children' | 'done' | 'onSkipIntro'> {
  /** Do 1º ao último. */
  ranked: PodiumEntry[]
  /** O que aparece no destaque de quem sabe menos (o último da lista). */
  worstLine: ReactNode
  /** A classificação completa, mostrada quando o pódio termina. */
  list: ReactNode
}

/** Fim de jogo em etapas: o pódio enche do 3º para o 1º, depois aparece quem sabe menos. */
export function PlayerPodium({ room, playerId, onPlayAgain, onLeave, ranked, worstLine, list }: PlayerPodiumProps) {
  const worst = ranked.length > 1 ? ranked[ranked.length - 1] : null
  const places = PODIUM_PLACES.filter((p) => p.place <= ranked.length)

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
    if (sound && !(stage === 1 && ranked.length < 3)) playSound(sound)
    // Só quando a etapa muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage])

  const done = stage >= PODIUM_STEPS.length

  return (
    <EndScreen room={room} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} done={done} onSkipIntro={() => setStage(PODIUM_STEPS.length)}>
      <div className="relative flex items-end justify-center gap-2" aria-label="Pódio">
        {stage >= 3 && <Confetti />}
        {places.map(({ place, label, step, order }) => {
          const entry = ranked[place - 1]
          const shown = revealed(place)
          return (
            <div key={place} className={`flex w-1/3 max-w-36 flex-col items-center gap-1.5 ${order}`}>
              <div className="relative flex min-h-36 w-full flex-col items-center justify-end gap-1 text-center">
                {shown ? (
                  <div key="shown" className="podium-card relative flex w-full flex-col items-center gap-1">
                    <div className="relative">
                      <img src={avatarUrl(entry.player)} alt="" className={place === 1 ? 'size-20' : 'size-16'} />
                      {place === 1 && <img src={coroa} alt="" className="icon-bounce absolute -top-5 -right-5 size-10" />}
                    </div>
                    <span className="w-full truncate font-bold">{entry.player.nickname}</span>
                    <span className="font-display text-xl text-brand">{entry.caption}</span>
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

      {worst && stage >= 4 && <Spotlight title="Quem sabe menos" icon={haha} player={worst.player} line={worstLine} tone="text-red-300" />}

      {done && list}
    </EndScreen>
  )
}

/** Um jogador em destaque, com o ícone do lado do avatar e uma linha embaixo. */
export function Spotlight({ title, icon, player, line, tone, winner = false }: { title: string; icon: string; player: PlayerView; line: ReactNode; tone: string; winner?: boolean }) {
  return (
    <div className="podium-card relative flex flex-col items-center gap-2 rounded-2xl bg-panel p-4 text-center">
      {winner && <Confetti />}
      <span className={`font-display text-lg tracking-wide ${tone}`}>{title}</span>
      <div className="relative">
        <img src={avatarUrl(player)} alt="" className="size-20" />
        <img src={icon} alt="" className={`absolute -top-4 -right-6 size-11 ${winner ? 'icon-bounce' : 'icon-wobble'}`} />
      </div>
      <span className="w-full truncate text-lg font-bold">{player.nickname}</span>
      <span className="font-hand text-lg font-medium text-chalk">{line}</span>
    </div>
  )
}

interface SkipButtonProps {
  /** Quem já pulou. */
  ready: string[]
  players: PlayerView[]
  playerId: string | null
  onSkip: () => Promise<string | null>
  className?: string
}

/** O Pular da revelação, igual em todos os modos: quando todos os conectados tocam, a próxima vem. */
export function SkipButton({ ready, players, playerId, onSkip, className = '' }: SkipButtonProps) {
  const [skipped, setSkipped] = useState(false)
  const connected = players.filter((p) => p.connected)
  const readyCount = connected.filter((p) => ready.includes(p.id)).length
  const isReady = skipped || (playerId !== null && ready.includes(playerId))
  return (
    <button
      onClick={async () => {
        playSound('skip')
        setSkipped(true)
        if (await onSkip()) setSkipped(false)
      }}
      disabled={isReady}
      className={`btn-3d btn-sm shrink-0 rounded-xl px-3 py-1.5 text-sm font-semibold ${isReady ? 'btn-dark is-pressed text-steel' : 'btn-dark text-chalk'} ${className}`}
    >
      {isReady ? 'Pronto' : 'Pular'}
      <span className="block text-xs text-steel">
        {readyCount}/{connected.length}
      </span>
    </button>
  )
}
