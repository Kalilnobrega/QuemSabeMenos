import { useEffect, type ReactNode } from 'react'
import { draftValue, erase, formatDraft, toggleSign, typeComma, typeDigits } from '../lib/guessDraft'

interface Props {
  draft: string
  unit: string | null | undefined
  disabled: boolean
  physicalKeys: boolean
  onChange: (draft: string) => void
  onSubmit: () => void
}

/** O teclado do Chutômetro: o mesmo em qualquer aparelho. Com `physicalKeys`, as teclas do computador também digitam. */
export function EstimateKeypad({ draft, unit, disabled, physicalKeys, onChange, onSubmit }: Props) {
  const ready = !disabled && draftValue(draft) !== null

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
      onChange(next)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [draft, disabled, physicalKeys, ready, onChange, onSubmit])

  const digit = (value: string) => (
    <Key
      key={value}
      disabled={disabled}
      onPress={() => {
        onChange(typeDigits(draft, value))
      }}
    >
      {value}
    </Key>
  )

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

      <div className="grid grid-cols-3 gap-2">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(digit)}
        <Key
          disabled={disabled}
          label="Vírgula"
          onPress={() => {
            onChange(typeComma(draft))
          }}
        >
          ,
        </Key>
        {digit('0')}
        {digit('000')}
        <Key
          disabled={disabled}
          label="Número negativo"
          pressed={draft.startsWith('-')}
          onPress={() => {
            onChange(toggleSign(draft))
          }}
        >
          −
        </Key>
        <Key
          disabled={disabled}
          label="Apagar"
          wide
          onPress={() => {
            onChange(erase(draft))
          }}
        >
          ⌫
        </Key>
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
  label,
  pressed,
  wide,
  onPress,
}: {
  children: ReactNode
  disabled: boolean
  label?: string
  pressed?: boolean
  wide?: boolean
  onPress: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={label}
      aria-pressed={pressed}
      // O foco fica fora da tecla, para o Enter chutar em vez de repetir o último toque.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onPress}
      className={`btn-3d btn-sm h-11 touch-manipulation rounded-xl font-display text-2xl select-none ${wide ? 'col-span-2' : ''} ${pressed ? 'btn-brand is-pressed text-ink' : 'btn-dark text-chalk'}`}
    >
      {children}
    </button>
  )
}
