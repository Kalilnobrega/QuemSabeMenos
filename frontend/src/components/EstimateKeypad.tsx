import { useEffect, useRef, useState, type PointerEvent, type ReactElement, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { reducedMotion, vibrate } from '../lib/effects'
import { draftValue, erase, formatDraft, toggleSign, typeComma, typeDigits } from '../lib/guessDraft'
import { seededShuffle } from '../lib/powerups'
import { playSound } from '../lib/sounds'
import { avatarUrl } from '../lib/avatars'
import type { EstimateMath, MathKey, PlayerView } from '../types/events'
import { ScratchCard } from './PowerUps'

// O teclado é bem maior que a pergunta: raspado como ela, tomaria os 20 segundos inteiros.
const KEYPAD_SCRATCH_RADIUS = 22
const KEYPAD_SCRATCH_REVEAL = 0.75
const RUNAWAY_SPEED = [50, 110] // px por segundo: dá para pegar, mas não fica parada
const RUNAWAY_DROP_MARGIN = 14 // px de folga em volta do espaço, para soltar com o dedo

interface Props {
  draft: string
  unit: string | null | undefined
  disabled: boolean
  physicalKeys: boolean
  compact: boolean // com poderes, os avisos ocupam parte da tela
  hotDigits: string[] // Tecla quente: os algarismos que acendem
  brokenKeys: readonly string[] // Tecla quebrada: parecem normais e racham no primeiro toque
  doubleKeys: readonly string[] // Duplo clique: parecem normais e digitam duas vezes
  shuffleSeed: number | null // Teclado mentiroso: com semente, as teclas trocam de lugar
  noErase: boolean // Perfeccionista: apagar não funciona
  covered: boolean // Raspadinha: as teclas só funcionam depois de raspadas
  shorted: boolean // Curto-circuito: as teclas morrem, e o Chutar ainda envia o que está no visor
  runaway: boolean // Teclas fugitivas: só funcionam depois de postas de volta no lugar
  onChange: (draft: string) => void
  onSubmit: () => void
}

/** O teclado do Chutômetro: o mesmo em qualquer aparelho. Com `physicalKeys`, as teclas do computador também digitam. */
export function EstimateKeypad({
  draft,
  unit,
  disabled,
  physicalKeys,
  compact,
  hotDigits,
  brokenKeys,
  doubleKeys,
  shuffleSeed,
  noErase,
  covered,
  shorted,
  runaway,
  onChange,
  onSubmit,
}: Props) {
  const ready = !disabled && draftValue(draft) !== null
  const [cracked, setCracked] = useState<string[]>([])
  const [caught, setCaught] = useState<string[]>([])
  const slots = useRef(new Map<string, HTMLElement>())

  useEffect(() => {
    if (disabled || !physicalKeys) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      const onButton = event.target instanceof Element && event.target.closest('button, a') !== null
      let next: string | null = null
      if (/^\d$/.test(event.key)) next = typeDigits(draft, event.key)
      else if (event.key === ',' || event.key === '.') next = typeComma(draft)
      else if (event.key === '-' || event.key === '−') next = toggleSign(draft)
      else if (event.key === 'Backspace' || event.key === 'Delete') next = erase(draft)
      else if (event.key === 'Enter' && !onButton && !event.repeat && ready) {
        event.preventDefault()
        onSubmit()
        return
      }
      if (next === null) return
      event.preventDefault()
      playSound(event.key === 'Backspace' || event.key === 'Delete' ? 'keypadErase' : 'keypadPress')
      onChange(next)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [draft, disabled, physicalKeys, ready, onChange, onSubmit])

  const digit = (value: string) => (
    <Key
      key={value}
      disabled={disabled}
      compact={compact}
      shorted={shorted}
      hot={hotDigits.includes(value[0])}
      cracked={cracked.includes(value)}
      onPress={() => {
        if (brokenKeys.includes(value)) {
          setCracked([...cracked, value])
          playSound('keyCrack')
          vibrate(80)
          return
        }
        const typed = doubleKeys.includes(value) ? value + value : value
        playSound('keypadPress', typed.length)
        onChange(typeDigits(draft, typed))
      }}
    >
      {value}
    </Key>
  )

  const keys: ReactElement<KeyProps>[] = [
    ...['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(digit),
    <Key
      key="comma"
      disabled={disabled}
      compact={compact}
      shorted={shorted}
      label="Vírgula"
      onPress={() => {
        playSound('keypadPress')
        onChange(typeComma(draft))
      }}
    >
      ,
    </Key>,
    digit('0'),
    digit('000'),
    <Key
      key="sign"
      disabled={disabled}
      compact={compact}
      shorted={shorted}
      label="Número negativo"
      pressed={draft.startsWith('-')}
      onPress={() => {
        playSound('keypadPress')
        onChange(toggleSign(draft))
      }}
    >
      −
    </Key>,
    <Key
      key="erase"
      disabled={disabled}
      compact={compact}
      shorted={shorted}
      label={noErase ? 'Apagar bloqueado' : 'Apagar'}
      wide
      locked={noErase}
      onPress={() => {
        playSound('keypadErase')
        onChange(erase(draft))
      }}
    >
      ⌫
    </Key>,
  ]

  return (
    <div className="flex flex-col gap-2.5">
      <output
        aria-label="Seu chute"
        className="flex min-h-14 flex-wrap items-center justify-center gap-x-2 rounded-xl bg-panel px-4 py-2 text-center"
      >
        {draft ? (
          <span className={`font-display text-chalk ${draft.length > 10 ? 'text-2xl' : 'text-4xl'}`}>
            {formatDraft(draft)}
          </span>
        ) : (
          <span className="font-display text-2xl text-steel/60">Seu chute</span>
        )}
        {unit && <span className="text-sm font-semibold text-steel">{unit}</span>}
      </output>

      {/* dense: a tecla larga pode cair no fim da linha, e o buraco é preenchido pela próxima. */}
      <ScratchCard
        active={covered}
        className={covered ? 'pb-1' : ''}
        radius={KEYPAD_SCRATCH_RADIUS}
        revealAt={KEYPAD_SCRATCH_REVEAL}
      >
        <div className="grid grid-flow-row-dense grid-cols-3 gap-2">
          {(shuffleSeed === null ? keys : seededShuffle(keys, shuffleSeed)).map((element) => {
            const id = String(element.key)
            if (!runaway || caught.includes(id)) return element
            const { children, wide } = element.props
            return (
              <div
                key={id}
                ref={(slot) => {
                  if (slot) slots.current.set(id, slot)
                  else slots.current.delete(id)
                }}
                className={`flex ${compact ? 'h-10' : 'h-11'} items-center justify-center rounded-xl border-2 border-dashed border-raised-edge font-display text-2xl text-steel select-none ${wide ? 'col-span-2' : ''}`}
              >
                {children}
              </div>
            )
          })}
        </div>
      </ScratchCard>

      {shorted && (
        <p className="text-center text-sm font-semibold text-danger" role="status">
          {draftValue(draft) === null
            ? 'Curto-circuito! O teclado queimou antes do seu chute.'
            : 'Curto-circuito! Só dá para chutar o que está no visor.'}
        </p>
      )}

      {runaway &&
        !shorted &&
        keys
          .filter((element) => !caught.includes(String(element.key)))
          .map((element) => {
            const id = String(element.key)
            return (
              <RunawayKey
                key={id}
                label={element.props.label ?? String(element.props.children)}
                hot={element.props.hot}
                slot={() => slots.current.get(id)}
                onCatch={() => {
                  playSound('keypadPress')
                  setCaught((list) => [...list, id])
                }}
              >
                {element.props.children}
              </RunawayKey>
            )
          })}

      <button
        type="button"
        disabled={!ready}
        onMouseDown={(event) => event.preventDefault()}
        onClick={onSubmit}
        className={`btn-3d btn-brand touch-manipulation rounded-xl py-2.5 font-display text-2xl tracking-wide text-ink ${ready ? '' : 'opacity-50'}`}
      >
        Chutar!
      </button>
    </div>
  )
}

/**
 * Teclas fugitivas: a tecla sai do espaço dela e fica batendo nas bordas da tela. Segurar para ela,
 * e soltar em cima do espaço dela a devolve ao teclado; soltar em outro lugar a faz fugir de novo.
 */
function RunawayKey({
  children,
  label,
  hot,
  slot,
  onCatch,
}: {
  children: ReactNode
  label: string
  hot?: boolean
  slot: () => HTMLElement | undefined
  onCatch: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const held = useRef<{ dx: number; dy: number } | null>(null)
  const motion = useRef({ x: 0, y: 0, vx: 0, vy: 0 })

  const launch = () => {
    const [low, high] = RUNAWAY_SPEED
    const speed = reducedMotion() ? 0 : low + Math.random() * (high - low)
    const angle = Math.random() * Math.PI * 2
    motion.current.vx = Math.cos(angle) * speed
    motion.current.vy = Math.sin(angle) * speed
  }
  const place = () => {
    if (ref.current) ref.current.style.transform = `translate(${motion.current.x}px, ${motion.current.y}px)`
  }

  useEffect(() => {
    const element = ref.current
    const home = slot()?.getBoundingClientRect()
    if (!element || !home) return
    element.style.width = `${home.width}px`
    element.style.height = `${home.height}px`
    motion.current.x = home.left
    motion.current.y = home.top
    launch()
    place()
    let frame = 0
    let last = performance.now()
    const step = (now: number) => {
      const seconds = Math.min(0.05, (now - last) / 1000)
      last = now
      if (!held.current) {
        const m = motion.current
        const maxX = window.innerWidth - home.width
        const maxY = window.innerHeight - home.height
        m.x += m.vx * seconds
        m.y += m.vy * seconds
        if (m.x < 0 || m.x > maxX) m.vx = m.x < 0 ? Math.abs(m.vx) : -Math.abs(m.vx)
        if (m.y < 0 || m.y > maxY) m.vy = m.y < 0 ? Math.abs(m.vy) : -Math.abs(m.vy)
        place()
      }
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
    // Só uma vez: a tecla continua voando quando o rascunho do chute muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const grab = (event: PointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    held.current = { dx: event.clientX - motion.current.x, dy: event.clientY - motion.current.y }
  }
  const drag = (event: PointerEvent<HTMLButtonElement>) => {
    if (!held.current) return
    motion.current.x = event.clientX - held.current.dx
    motion.current.y = event.clientY - held.current.dy
    place()
  }
  const drop = (event: PointerEvent<HTMLButtonElement>) => {
    if (!held.current) return
    held.current = null
    const home = slot()?.getBoundingClientRect()
    const onHome =
      home &&
      event.clientX >= home.left - RUNAWAY_DROP_MARGIN &&
      event.clientX <= home.right + RUNAWAY_DROP_MARGIN &&
      event.clientY >= home.top - RUNAWAY_DROP_MARGIN &&
      event.clientY <= home.bottom + RUNAWAY_DROP_MARGIN
    if (onHome) onCatch()
    else launch()
  }

  return createPortal(
    <button
      ref={ref}
      type="button"
      aria-label={`Pegar a tecla ${label}`}
      onPointerDown={grab}
      onPointerMove={drag}
      onPointerUp={drop}
      onPointerCancel={drop}
      className={`btn-3d btn-sm fixed top-0 left-0 z-40 cursor-grab touch-none rounded-xl font-display text-2xl select-none ${hot ? 'btn-brand text-ink' : 'btn-dark text-chalk'}`}
    >
      {children}
    </button>,
    document.body,
  )
}

interface KeyProps {
  children: ReactNode
  disabled: boolean
  compact: boolean
  shorted: boolean
  label?: string
  pressed?: boolean
  wide?: boolean
  hot?: boolean
  cracked?: boolean // Tecla quebrada: já rachou, não digita mais
  locked?: boolean // Perfeccionista: bloqueada desde o início
  onPress: () => void
}

function Key({ children, disabled, compact, shorted, label, pressed, wide, hot, cracked, locked, onPress }: KeyProps) {
  const dead = cracked || locked
  const tone = pressed ? 'btn-brand is-pressed text-ink' : hot ? 'btn-brand text-ink' : 'btn-dark text-chalk'
  return (
    <button
      type="button"
      disabled={disabled || shorted}
      aria-label={cracked ? `${children} quebrada` : label}
      aria-pressed={pressed}
      // O foco fica fora da tecla, para o Enter chutar em vez de repetir o último toque.
      onMouseDown={(event) => event.preventDefault()}
      onClick={
        dead
          ? () => {
              playSound(cracked ? 'keyDead' : 'keypadErase')
              vibrate(40)
            }
          : onPress
      }
      className={`btn-3d btn-sm ${compact ? 'h-10' : 'h-11'} touch-manipulation rounded-xl font-display text-2xl select-none ${wide ? 'col-span-2' : ''} ${tone} ${cracked ? 'key-crack relative overflow-hidden' : ''} ${locked ? 'line-through opacity-40' : ''} ${shorted ? 'key-short opacity-25' : ''}`}
    >
      <span className={cracked ? 'opacity-50' : ''}>{children}</span>
      {cracked && <Crack flip={String(children).length % 2 === 0 || Number(children) % 2 === 0} />}
    </button>
  )
}

/** A rachadura por cima da tecla: uma linha quebrada de cima a baixo, com dois galhos e um brilho na borda. */
function Crack({ flip }: { flip: boolean }) {
  const lines = 'M62 -2 54 11 66 18 49 29 57 46M54 11 37 7M66 18 84 24 92 17M49 29 32 34'
  return (
    <svg
      viewBox="0 0 110 44"
      preserveAspectRatio="xMidYMid slice"
      className={`pointer-events-none absolute inset-0 size-full ${flip ? '-scale-x-100' : ''}`}
      fill="none"
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path
        d={lines}
        className="key-crack-line"
        pathLength={100}
        stroke="var(--color-chalk)"
        strokeOpacity={0.4}
        strokeWidth={3.6}
        transform="translate(0.9 0.9)"
      />
      <path d={lines} className="key-crack-line" pathLength={100} stroke="var(--color-ink)" strokeWidth={2.4} />
    </svg>
  )
}

const MATH_OP_SYMBOL = { add: '+', sub: '−', mul: '×', div: '÷' }
const MATH_MAX = 1e12 // acima disso o visor não cabe

function mathLabel({ op, value }: MathKey) {
  if (op === 'square') return 'x²'
  if (op === 'sqrt') return '√'
  return `${MATH_OP_SYMBOL[op]}${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(value ?? 0)}`
}

/** A conta de uma tecla, com 3 casas no máximo; null quando ela não dá nesse número. */
function applyMath(current: number, { op, value }: MathKey) {
  const operand = value ?? 0
  const results = {
    add: current + operand,
    sub: current - operand,
    mul: current * operand,
    div: current / operand,
    square: current ** 2,
    sqrt: Math.sqrt(current),
  }
  const result = Math.round(results[op] * 1000) / 1000
  return Number.isFinite(result) && Math.abs(result) <= MATH_MAX ? result : null
}

/**
 * Matemática: 9 teclas de conta no lugar do teclado, cada uma com poucos usos, e o visor começa num
 * número sorteado. Voltar desfaz o último passo e devolve o uso. Cada conta vai para o servidor: quem já
 * chutou assiste, e se o tempo acabar vale o que está no visor.
 */
export function MathKeypad({
  puzzle,
  unit,
  covered,
  shorted,
  onSteps,
  onSubmit,
}: {
  puzzle: EstimateMath
  unit: string | null | undefined
  covered: boolean
  shorted: boolean
  onSteps: (steps: number[]) => void
  onSubmit: (value: number) => void
}) {
  // Começa do que o servidor guardou, para não perder as contas ao reconectar.
  const [steps, setSteps] = useState(puzzle.steps ?? [])
  const value = steps.reduce((current, index) => applyMath(current, puzzle.keys[index]) ?? current, puzzle.start)
  const change = (next: number[]) => {
    setSteps(next)
    onSteps(next)
  }

  return (
    <div className="flex flex-col gap-2.5">
      <output
        aria-label="Seu chute"
        className="flex min-h-14 flex-wrap items-center justify-center gap-x-2 rounded-xl bg-panel px-4 py-2 text-center"
      >
        <span className="font-display text-4xl text-chalk">
          {new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(value)}
        </span>
        {unit && <span className="text-sm font-semibold text-steel">{unit}</span>}
      </output>

      <ScratchCard
        active={covered}
        className={covered ? 'pb-1' : ''}
        radius={KEYPAD_SCRATCH_RADIUS}
        revealAt={KEYPAD_SCRATCH_REVEAL}
      >
        <div className="grid grid-cols-3 gap-2">
          {puzzle.keys.map((key, index) => {
            const left = key.uses - steps.filter((step) => step === index).length
            const useless = left === 0 || applyMath(value, key) === null
            return (
              <button
                key={`${key.op}-${key.value}`}
                type="button"
                disabled={useless || shorted}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  playSound('keypadPress')
                  change([...steps, index])
                }}
                aria-label={`${mathLabel(key)}, ${left} ${left === 1 ? 'uso' : 'usos'}`}
                className={`btn-3d btn-sm btn-dark relative h-11 touch-manipulation rounded-xl font-display text-xl text-chalk select-none ${useless ? 'opacity-40' : ''} ${shorted ? 'key-short opacity-25' : ''}`}
              >
                {mathLabel(key)}
                <span className="absolute top-0.5 right-1.5 font-sans text-xs font-semibold text-brand">{left}</span>
              </button>
            )
          })}
          <button
            type="button"
            disabled={steps.length === 0 || shorted}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              playSound('keypadErase')
              change(steps.slice(0, -1))
            }}
            className={`btn-3d btn-sm btn-dark col-span-3 h-11 touch-manipulation rounded-xl font-display text-xl text-chalk select-none ${steps.length === 0 ? 'opacity-40' : ''} ${shorted ? 'key-short opacity-25' : ''}`}
          >
            ⟲ Voltar
          </button>
        </div>
      </ScratchCard>

      {shorted && (
        <p className="text-center text-sm font-semibold text-danger" role="status">
          Curto-circuito! Só dá para chutar o que está no visor.
        </p>
      )}

      <button
        type="button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => onSubmit(value)}
        className="btn-3d btn-brand touch-manipulation rounded-xl py-2.5 font-display text-2xl tracking-wide text-ink"
      >
        Chutar!
      </button>
    </div>
  )
}

/** Para quem já chutou ou ficou sem tempo: as contas do alvo da Matemática, ao vivo. */
export function MathWatchPanel({
  math,
  unit,
  player,
}: {
  math: EstimateMath
  unit: string | null | undefined
  player: PlayerView | undefined
}) {
  const steps = math.steps ?? []
  return (
    <div className="flex w-full flex-col gap-2 rounded-xl bg-panel p-3">
      <p className="flex items-center justify-center gap-2 text-sm font-semibold text-steel">
        {player && <img src={avatarUrl(player)} alt="" className="size-7" />}
        {player?.nickname ?? 'Alguém'} está fazendo contas
      </p>
      <p className="text-center font-display text-4xl text-chalk" aria-live="polite">
        {new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(math.value)}
        {unit && <span className="ml-2 font-sans text-sm font-semibold text-steel">{unit}</span>}
      </p>
      <p className="min-h-5 text-center text-sm break-words text-steel">
        {steps.length > 0 &&
          `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(math.start)} ${steps
            .map((index) => mathLabel(math.keys[index]))
            .join(' ')}`}
      </p>
      <ul className="grid grid-cols-3 gap-1.5" aria-label="Teclas do alvo">
        {math.keys.map((key, index) => {
          const left = key.uses - steps.filter((step) => step === index).length
          return (
            <li
              key={`${key.op}-${key.value}`}
              className={`relative rounded-lg bg-raised py-1 text-center font-display text-chalk ${left === 0 ? 'opacity-40' : ''}`}
            >
              {mathLabel(key)}
              <span className="absolute top-0 right-1 font-sans text-xs font-semibold text-brand">{left}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
