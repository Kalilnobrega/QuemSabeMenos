import { useEffect, useState, type ReactNode } from 'react'
import { vibrate } from '../lib/effects'
import { draftValue, erase, formatDraft, toggleSign, typeComma, typeDigits } from '../lib/guessDraft'
import { seededShuffle } from '../lib/powerups'
import { playSound } from '../lib/sounds'

interface Props {
  draft: string
  unit: string | null | undefined
  disabled: boolean
  physicalKeys: boolean
  compact: boolean // com poderes, os avisos ocupam parte da tela
  hotDigits: string[] // Tecla quente: os algarismos que acendem
  brokenKeys: readonly string[] // Tecla quebrada: parecem normais e racham no primeiro toque
  shuffleSeed: number | null // Teclado mentiroso: com semente, as teclas trocam de lugar
  noErase: boolean // Perfeccionista: apagar não funciona
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
  shuffleSeed,
  noErase,
  onChange,
  onSubmit,
}: Props) {
  const ready = !disabled && draftValue(draft) !== null
  const [cracked, setCracked] = useState<string[]>([])

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
      hot={hotDigits.includes(value[0])}
      cracked={cracked.includes(value)}
      onPress={() => {
        if (brokenKeys.includes(value)) {
          setCracked([...cracked, value])
          playSound('keyCrack')
          vibrate(80)
          return
        }
        playSound('keypadPress', value.length)
        onChange(typeDigits(draft, value))
      }}
    >
      {value}
    </Key>
  )

  const keys = [
    ...['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(digit),
    <Key
      key="comma"
      disabled={disabled}
      compact={compact}
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
      <div className="grid grid-flow-row-dense grid-cols-3 gap-2">
        {shuffleSeed === null ? keys : seededShuffle(keys, shuffleSeed)}
      </div>

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

function Key({
  children,
  disabled,
  compact,
  label,
  pressed,
  wide,
  hot,
  cracked,
  locked,
  onPress,
}: {
  children: ReactNode
  disabled: boolean
  compact: boolean
  label?: string
  pressed?: boolean
  wide?: boolean
  hot?: boolean
  cracked?: boolean // Tecla quebrada: já rachou, não digita mais
  locked?: boolean // Perfeccionista: bloqueada desde o início
  onPress: () => void
}) {
  const dead = cracked || locked
  const tone = pressed ? 'btn-brand is-pressed text-ink' : hot ? 'btn-brand text-ink' : 'btn-dark text-chalk'
  return (
    <button
      type="button"
      disabled={disabled}
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
      className={`btn-3d btn-sm ${compact ? 'h-10' : 'h-11'} touch-manipulation rounded-xl font-display text-2xl select-none ${wide ? 'col-span-2' : ''} ${tone} ${cracked ? 'key-crack relative overflow-hidden' : ''} ${locked ? 'line-through opacity-40' : ''}`}
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
