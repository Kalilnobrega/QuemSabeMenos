import { useEffect, useRef, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import { LeaveButton } from './LeaveButton'
import { AVATAR_URLS } from '../lib/avatars'
import { playSound } from '../lib/sounds'
import type { RoomSettings, RoomState, UpdateSettingsRequest } from '../types/events'

const MODES: Record<RoomSettings['mode'], { name: string; hint: string }> = {
  classic: { name: 'Clássico', hint: 'Só as perguntas: quem sabe mais, ganha.' },
  powers: { name: 'Clássico com poderes', hint: 'Com poderes que podem te ajudar ou atrapalhar a galera.' },
  last_standing: { name: 'Último de pé', hint: 'Verdadeiro ou falso com 2 vidas. Sobraram dois, é X1.' },
}

interface Props {
  room: RoomState
  playerId: string | null
  onLeave: () => void
  onStart: () => Promise<string | null>
  onUpdateSettings: (patch: UpdateSettingsRequest) => Promise<string | null>
}

function inviteUrl(code: string) {
  return `${window.location.origin}/sala/${code}`
}

export function Lobby({ room, playerId, onLeave, onStart, onUpdateSettings }: Props) {
  const [notice, setNotice] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const isHost = room.host_id === playerId

  const playerCount = useRef(room.players.length)
  useEffect(() => {
    const count = room.players.length
    if (count > playerCount.current) playSound('join')
    else if (count < playerCount.current) playSound('leave')
    playerCount.current = count
  }, [room.players.length])
  const enoughPlayers = room.players.length >= room.min_players

  const invite = async () => {
    const url = inviteUrl(room.code)
    try {
      if (navigator.share) {
        await navigator.share({ title: 'Quem Sabe Menos?', text: `Entra na minha sala: ${room.code}`, url })
        return
      }
      await navigator.clipboard.writeText(url)
      setNotice('Link copiado!')
    } catch (e) {
      // Fechar o menu de compartilhar não é erro.
      if (e instanceof DOMException && e.name === 'AbortError') return
      setNotice(`Não deu para copiar. O link é ${url}`)
    }
  }

  const start = async () => {
    setStarting(true)
    setNotice(await onStart())
    setStarting(false)
  }

  const { themes, theme_options: themeOptions } = room.settings
  const allThemes = themes.length === themeOptions.length
  const powers = room.settings.mode === 'powers'
  const themesLabel = allThemes ? 'Todos' : themes.length <= 2 ? themes.join(', ') : `${themes.length} temas`
  const summary =
    room.settings.mode === 'last_standing'
      ? [
          { label: 'Frases', value: 'V ou F' },
          { label: 'Vidas', value: '2' },
          { label: 'Temas', value: themesLabel },
        ]
      : [
          { label: 'Perguntas', value: String(room.settings.rounds) },
          { label: 'Resposta', value: `${room.settings.answer_seconds}s` },
          { label: 'QI cheio', value: room.settings.speed_grace_seconds ? `${room.settings.speed_grace_seconds}s` : 'Não' },
          ...(powers ? [{ label: 'Poderes', value: `até ${room.settings.powerup_max}` }] : []),
          { label: 'Temas', value: themesLabel },
        ]

  return (
    <section className="flex w-full flex-col gap-6">
      <header className="flex flex-col items-center gap-3 rounded-2xl bg-panel p-5">
        <span className="text-sm font-semibold tracking-widest text-steel uppercase">Código da sala</span>
        <span className="font-display text-6xl tracking-[0.25em] text-brand">{room.code}</span>
        <button onClick={invite} className="btn-3d btn-sm btn-light rounded-xl px-5 py-2 font-semibold text-ink">
          Convidar a galera
        </button>
      </header>

      <div className="flex flex-col gap-3">
        <h2 className="flex items-baseline justify-between font-display text-2xl tracking-wide">
          Jogadores
          <span className="font-sans text-base text-steel">
            {room.players.length}/{room.max_players}
          </span>
        </h2>
        <ul className="flex flex-col gap-2">
          {room.players.map((player) => (
            <li
              key={player.id}
              className={`flex items-center gap-3 rounded-xl bg-panel px-3 py-2 ${player.connected ? '' : 'opacity-50'}`}
            >
              <img src={AVATAR_URLS[player.avatar]} alt="" className="size-12" />
              <span className="flex-1 truncate text-lg font-semibold">
                {player.nickname}
                {player.id === playerId && <span className="ml-2 text-sm font-normal text-steel">(você)</span>}
              </span>
              {!player.connected && <span className="font-hand font-medium text-steel">reconectando…</span>}
              {player.id === room.host_id && (
                <img src={coroa} alt="Anfitrião" title="Anfitrião" className="size-8" />
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="font-display text-2xl tracking-wide">Partida</h2>
        <div className="flex flex-col items-center gap-0.5 rounded-xl bg-panel px-4 py-3 text-center">
          <span className="font-display text-xl tracking-wide text-brand">{MODES[room.settings.mode].name}</span>
          <span className="text-sm text-steel">{MODES[room.settings.mode].hint}</span>
        </div>
        <dl className="grid grid-cols-6 gap-2">
          {summary.map((item, index) => (
            <div
              key={item.label}
              // 3 por linha; na de baixo, os que sobram dividem a largura.
              className={`flex flex-col items-center justify-center rounded-xl bg-panel px-2 py-2 text-center ${
                index < 3 ? 'col-span-2' : summary.length === 4 ? 'col-span-6' : 'col-span-3'
              }`}
            >
              <dt className="text-xs font-semibold tracking-wide text-steel uppercase">{item.label}</dt>
              <dd className="font-display text-lg leading-tight text-chalk">{item.value}</dd>
            </div>
          ))}
        </dl>
        {isHost && (
          <button
            onClick={() => setSettingsOpen(true)}
            className="btn-3d btn-sm btn-dark flex items-center justify-center gap-2 rounded-xl py-3 font-semibold text-chalk"
          >
            <SettingsIcon />
            Configurações
          </button>
        )}
      </div>

      {notice && <p className="text-center text-steel">{notice}</p>}

      {isHost ? (
        <div className="flex flex-col gap-2">
          <button
            onClick={start}
            disabled={!enoughPlayers || starting}
            className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink disabled:opacity-50"
          >
            Começar partida
          </button>
          {!enoughPlayers && (
            <p className="text-center font-hand font-medium text-base text-steel">
              Precisa de pelo menos {room.min_players} jogadores. Chama a galera!
            </p>
          )}
        </div>
      ) : (
        <p className="text-center font-hand font-medium text-lg text-steel">Esperando o anfitrião começar…</p>
      )}

      <LeaveButton onLeave={onLeave} />

      {isHost && settingsOpen && (
        <SettingsSheet room={room} onUpdate={onUpdateSettings} onClose={() => setSettingsOpen(false)} />
      )}
    </section>
  )
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M4 6h16M4 12h16M4 18h16" opacity="0.45" />
      <circle cx="8" cy="6" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="16" cy="12" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="10" cy="18" r="2.4" fill="currentColor" stroke="none" />
    </svg>
  )
}

interface SettingsSheetProps {
  room: RoomState
  onUpdate: (patch: UpdateSettingsRequest) => Promise<string | null>
  onClose: () => void
}

/** Painel do anfitrião com as configurações da partida; cada toque já vale para a sala toda. */
function SettingsSheet({ room, onUpdate, onClose }: SettingsSheetProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const { settings } = room
  const { themes, theme_options: themeOptions } = settings
  const allThemes = themes.length === themeOptions.length

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const update = async (patch: UpdateSettingsRequest) => setNotice(await onUpdate(patch))
  const toggleTheme = (theme: string) => {
    if (themes.includes(theme) && themes.length === 1) {
      setNotice('Escolha pelo menos um tema.')
      return
    }
    update({ themes: themes.includes(theme) ? themes.filter((t) => t !== theme) : [...themes, theme] })
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-ink/70 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(e) => e.stopPropagation()}
        className="settings-sheet flex max-h-[90dvh] w-full max-w-md flex-col gap-5 overflow-y-auto rounded-t-3xl border border-white/10 bg-ink p-5 pb-8 sm:rounded-3xl"
      >
        <h2 id="settings-title" className="text-center font-display text-3xl tracking-wide text-brand">
          Configurações
        </h2>

        <div className="flex flex-col gap-2">
          <h3 className="font-display text-xl tracking-wide">Modo</h3>
          <div className="grid grid-cols-2 gap-2">
            {settings.mode_options.map((mode, index) => (
              <button
                key={mode}
                onClick={() => update({ mode })}
                aria-pressed={settings.mode === mode}
                // Número ímpar de modos: o último ocupa a linha inteira.
                className={`btn-3d btn-sm flex flex-col gap-0.5 rounded-lg px-3 py-2 text-left ${
                  index === settings.mode_options.length - 1 && index % 2 === 0 ? 'col-span-2' : ''
                } ${
                  settings.mode === mode ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel hover:text-chalk'
                }`}
              >
                <span className="font-semibold">{MODES[mode].name}</span>
                <span className="text-xs leading-snug opacity-80">{MODES[mode].hint}</span>
              </button>
            ))}
          </div>
        </div>

        {settings.mode === 'powers' && (
          <OptionRow
            title="Limite de poderes"
            hint="Quantas habilidades cada um pode guardar ao mesmo tempo"
            options={settings.powerup_max_options}
            value={settings.powerup_max}
            label={(n) => String(n)}
            onPick={(powerup_max) => update({ powerup_max })}
          />
        )}

        {settings.mode !== 'last_standing' && (
          <>
            <OptionRow
              title="Perguntas"
              hint="Mais a impossível no final"
              options={settings.round_options}
              value={settings.rounds}
              label={(n) => String(n)}
              onPick={(rounds) => update({ rounds })}
            />
            <OptionRow
              title="Tempo de resposta"
              hint="Segundos para escolher a alternativa"
              options={settings.answer_options}
              value={settings.answer_seconds}
              label={(n) => `${n}s`}
              onPick={(answer_seconds) => update({ answer_seconds })}
            />
            <OptionRow
              title="Tempo de QI cheio"
              hint="Quem acerta dentro desse tempo leva o máximo de QI"
              options={settings.grace_options}
              value={settings.speed_grace_seconds}
              label={(n) => (n ? `${n}s` : 'Não')}
              onPick={(speed_grace_seconds) => update({ speed_grace_seconds })}
            />
          </>
        )}

        <div className="flex flex-col gap-2">
          <h3 className="flex items-baseline justify-between font-display text-xl tracking-wide">
            Temas
            {!allThemes && (
              <button onClick={() => update({ themes: themeOptions })} className="font-sans text-sm font-semibold text-brand">
                Marcar todos
              </button>
            )}
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {themeOptions.map((theme) => {
              const selected = themes.includes(theme)
              return (
                <button
                  key={theme}
                  onClick={() => toggleTheme(theme)}
                  aria-pressed={selected}
                  className={`btn-3d btn-sm rounded-lg px-3 py-2 text-left font-semibold ${
                    selected ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel hover:text-chalk'
                  }`}
                >
                  {theme}
                </button>
              )
            })}
          </div>
        </div>

        {notice && <p className="text-center text-steel">{notice}</p>}

        <button onClick={onClose} className="btn-3d btn-brand rounded-xl py-3 font-display text-2xl tracking-wide text-ink">
          Pronto
        </button>
      </div>
    </div>
  )
}

interface OptionRowProps {
  title: string
  hint: string
  options: number[]
  value: number
  label: (option: number) => string
  onPick: (option: number) => void
}

function OptionRow({ title, hint, options, value, label, onPick }: OptionRowProps) {
  return (
    <div className="flex flex-col gap-2">
      <div>
        <h3 className="font-display text-xl tracking-wide">{title}</h3>
        <p className="text-sm text-steel">{hint}</p>
      </div>
      <div className="flex gap-2">
        {options.map((option) => (
          <button
            key={option}
            onClick={() => onPick(option)}
            aria-pressed={value === option}
            className={`btn-3d btn-sm flex-1 rounded-lg py-2 font-semibold ${
              value === option ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel hover:text-chalk'
            }`}
          >
            {label(option)}
          </button>
        ))}
      </div>
    </div>
  )
}
