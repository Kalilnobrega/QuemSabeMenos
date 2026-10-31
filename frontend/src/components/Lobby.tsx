import { useEffect, useRef, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import { LeaveButton } from './LeaveButton'
import { InfoButton, ModeGuide } from './ModeGuide'
import { AVATAR_NAMES, AVATARS, avatarUrl, type Avatar } from '../lib/avatars'
import { playSound } from '../lib/sounds'
import { TEAMS, teamName } from '../lib/teams'
import type { PlayerView, RoomSettings, RoomState, UpdateSettingsRequest } from '../types/events'

const MODES: Record<RoomSettings['mode'], { name: string; hint: string }> = {
  classic: { name: 'Clássico', hint: 'Todo mundo responde junto: quem sabe mais, ganha.' },
  specialist: { name: 'Especialista', hint: 'Um tema a cada 5 perguntas: quem escolhe ganha +25%.' },
  teams: { name: 'Times', hint: 'O time vota junto e tem um QI só.' },
  last_standing: { name: 'Último de pé', hint: 'Errou, perde uma vida. Sobraram dois, é X1.' },
  hot_potato: { name: 'Batata quente', hint: 'Um por vez: acertou, passa. Explodiu na mão, está fora.' },
  estimate: { name: 'Chutômetro', hint: 'A resposta é um número: quem chutar mais perto ganha QI.' },
}

// O Chutômetro vai até 20 perguntas: com mais, fica com o maior tamanho dele (como no servidor).
const ESTIMATE_ROUNDS = [10, 15, 20]
const estimateRounds = (rounds: number) => ESTIMATE_ROUNDS.filter((n) => n <= rounds).at(-1) ?? ESTIMATE_ROUNDS[0]

const POWERS_HINT: Record<RoomSettings['mode'], string> = {
  classic: 'Ajudas para você e sabotagens nos outros, ganhas acertando em sequência',
  specialist: 'Os do Clássico, com o Golpe no lugar do Tema',
  teams: 'O time guarda até 3, o capitão usa, e as sabotagens miram outro time',
  last_standing: 'Escudo segura vida, Roubo leva vida, e quem cai vira fantasma sabotador',
  hot_potato: 'Ajudas para quem está com a batata, sabotagens para quem assiste',
  estimate: 'Sem poderes por enquanto',
}

const SURVIVAL_KINDS: Record<RoomSettings['survival_kind'], { name: string; hint: string; lives: number }> = {
  true_false: { name: 'V ou F', hint: '3 vidas · médias, depois difíceis', lives: 3 },
  choices: { name: 'Alternativas', hint: '3 vidas · fáceis, médias, depois difíceis', lives: 3 },
}

interface Props {
  room: RoomState
  playerId: string | null
  onLeave: () => void
  onStart: () => Promise<string | null>
  onUpdateSettings: (patch: UpdateSettingsRequest) => Promise<string | null>
  onSetTeam: (playerId: string, team: number) => Promise<string | null>
  onUpdateAvatar: (avatar: Avatar) => Promise<string | null>
}

function inviteUrl(code: string) {
  return `${window.location.origin}/sala/${code}`
}

export function Lobby({ room, playerId, onLeave, onStart, onUpdateSettings, onSetTeam, onUpdateAvatar }: Props) {
  const [notice, setNotice] = useState<string | null>(null)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const me = room.players.find((p) => p.id === playerId)
  const [starting, setStarting] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)

  const isHost = room.host_id === playerId

  const playerCount = useRef(room.players.length)
  useEffect(() => {
    const count = room.players.length
    if (count > playerCount.current) playSound('join')
    else if (count < playerCount.current) playSound('leave')
    playerCount.current = count
  }, [room.players.length])
  const teamsMode = room.settings.mode === 'teams'
  const minPlayers = teamsMode ? Math.max(room.min_players, room.settings.team_count * 2) : room.min_players
  const enoughPlayers = room.players.length >= minPlayers

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
  const themesLabel = allThemes ? 'Todos' : themes.length <= 2 ? themes.join(', ') : `${themes.length} temas`
  const summary =
    teamsMode
      ? [
          { label: 'Times', value: String(room.settings.team_count) },
          { label: 'Montagem', value: room.settings.team_pick === 'host' ? 'Anfitrião' : 'Sorteio' },
          { label: 'Perguntas', value: String(room.settings.rounds) },
          { label: 'Poderes', value: room.settings.powers ? 'até 3' : 'Não' },
          { label: 'Temas', value: themesLabel },
        ]
      : room.settings.mode === 'hot_potato'
      ? [
          { label: 'Pavio', value: '40–60s' },
          { label: 'Erro', value: '−10s' },
          { label: 'Poderes', value: room.settings.powers ? `até ${room.settings.powerup_max}` : 'Não' },
          { label: 'Temas', value: themesLabel },
        ]
      : room.settings.mode === 'estimate'
      ? [
          { label: 'Perguntas', value: String(estimateRounds(room.settings.rounds)) },
          { label: 'Chute', value: '20s' },
          { label: 'Poderes', value: 'Não' },
          { label: 'Temas', value: themesLabel },
        ]
      : room.settings.mode === 'last_standing'
      ? [
          { label: 'Perguntas', value: SURVIVAL_KINDS[room.settings.survival_kind].name },
          { label: 'Vidas', value: String(SURVIVAL_KINDS[room.settings.survival_kind].lives) },
          { label: 'Poderes', value: room.settings.powers ? `até ${room.settings.powerup_max}` : 'Não' },
          { label: 'Temas', value: themesLabel },
        ]
      : [
          { label: 'Perguntas', value: String(room.settings.rounds) },
          { label: 'Resposta', value: `${room.settings.answer_seconds}s` },
          { label: 'QI cheio', value: room.settings.speed_grace_seconds ? `${room.settings.speed_grace_seconds}s` : 'Não' },
          { label: 'Poderes', value: room.settings.powers ? `até ${room.settings.powerup_max}` : 'Não' },
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
        {teamsMode && room.settings.team_pick === 'host' ? (
          <TeamBuilder room={room} playerId={playerId} isHost={isHost} onSetTeam={onSetTeam} onNotice={setNotice} onEditAvatar={() => setAvatarOpen(true)} />
        ) : (
        <ul className="flex flex-col gap-2">
          {room.players.map((player) => (
            <li
              key={player.id}
              className={`flex items-center gap-3 rounded-xl bg-panel px-3 py-2 ${player.connected ? '' : 'opacity-50'}`}
            >
              {player.id === playerId ? (
                <MyAvatar player={player} className="size-12" onClick={() => setAvatarOpen(true)} />
              ) : (
                <img src={avatarUrl(player)} alt="" className="size-12" />
              )}
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
        )}
        {teamsMode && room.settings.team_pick === 'random' && (
          <p className="text-center font-hand font-medium text-steel">Os times são sorteados quando a partida começar.</p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="font-display text-2xl tracking-wide">Partida</h2>
        <div className="relative flex flex-col items-center gap-0.5 rounded-xl bg-panel px-11 py-3 text-center">
          <span className="font-display text-xl tracking-wide text-brand">
            {MODES[room.settings.mode].name}
            {(room.settings.mode === 'classic' || room.settings.mode === 'specialist') && room.settings.powers && ' com poderes'}
          </span>
          <span className="text-sm text-steel">{MODES[room.settings.mode].hint}</span>
          <span className="absolute top-2 right-2 text-steel">
            <InfoButton onClick={() => setGuideOpen(true)} label={`Como funciona o ${MODES[room.settings.mode].name}`} />
          </span>
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
              {teamsMode ? `${room.settings.team_count} times precisam de pelo menos ${minPlayers} jogadores.` : `Precisa de pelo menos ${minPlayers} jogadores.`} Chama a galera!
            </p>
          )}
        </div>
      ) : (
        <p className="text-center font-hand font-medium text-lg text-steel">Esperando o anfitrião começar…</p>
      )}

      <LeaveButton onLeave={onLeave} />

      {guideOpen && <ModeGuide mode={room.settings.mode} onClose={() => setGuideOpen(false)} />}

      {isHost && settingsOpen && (
        <SettingsSheet room={room} onUpdate={onUpdateSettings} onClose={() => setSettingsOpen(false)} />
      )}
      {avatarOpen && me && (
        <AvatarSheet room={room} me={me} onPick={onUpdateAvatar} onClose={() => setAvatarOpen(false)} />
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
/** O seu avatar no lobby, com o lápis: tocou, abre a troca de bicho. É um span porque a linha dos
 * times já é um botão (mover de time). */
function MyAvatar({ player, className, onClick }: { player: PlayerView; className: string; onClick: () => void }) {
  return (
    <span
      role="button"
      tabIndex={0}
      aria-label="Trocar meu bicho"
      title="Trocar meu bicho"
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return
        e.preventDefault()
        e.stopPropagation()
        onClick()
      }}
      className="relative inline-flex shrink-0 cursor-pointer rounded-full transition hover:scale-105"
    >
      <img src={avatarUrl(player)} alt="" className={className} />
      <span className="absolute -right-1 -bottom-1 flex size-5 items-center justify-center rounded-full border-2 border-ink bg-brand">
        <svg viewBox="0 0 16 16" className="size-3" aria-hidden="true">
          <path d="M10.5 2.5 13.5 5.5 6 13H3v-3Z" fill="#12141B" />
          <path d="m9.2 3.8 3 3" stroke="#FFC107" strokeWidth="1.2" />
        </svg>
      </span>
    </span>
  )
}

/** Trocar de bicho no lobby. Bicho que alguém já usa pode: você fica com uma cor de fundo diferente. */
function AvatarSheet({ room, me, onPick, onClose }: { room: RoomState; me: PlayerView; onPick: Props['onUpdateAvatar']; onClose: () => void }) {
  const [notice, setNotice] = useState<string | null>(null)
  const earlier = room.players.slice(0, room.players.findIndex((p) => p.id === me.id))
  const others = room.players.filter((p) => p.id !== me.id)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const pick = async (avatar: Avatar) => {
    playSound('select')
    const error = await onPick(avatar)
    if (error) setNotice(error)
    else onClose()
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-ink/70 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="avatar-title"
        onClick={(e) => e.stopPropagation()}
        className="settings-sheet flex max-h-[90dvh] w-full max-w-md flex-col gap-4 overflow-y-auto rounded-t-3xl border border-white/10 bg-ink p-5 pb-8 sm:rounded-3xl"
      >
        <h2 id="avatar-title" className="text-center font-display text-3xl tracking-wide text-brand">
          Escolha seu bicho
        </h2>
        <p className="text-center text-sm text-steel">Pode repetir o de alguém: o seu ganha outra cor de fundo.</p>
        <div className="grid grid-cols-4 gap-3">
          {AVATARS.map((avatar) => {
            const selected = me.avatar === avatar
            // A cor que você teria com esse bicho: conta quem chegou antes e já usa ele.
            const preview = selected ? me : { avatar, avatar_variant: earlier.filter((p) => p.avatar === avatar).length }
            const users = others.filter((p) => p.avatar === avatar)
            return (
              <button
                key={avatar}
                onClick={() => (selected ? onClose() : void pick(avatar))}
                aria-label={AVATAR_NAMES[avatar]}
                aria-pressed={selected}
                className={`relative rounded-full p-1 ${selected ? 'scale-105 ring-4 ring-brand' : 'opacity-80 hover:opacity-100'}`}
              >
                <img src={avatarUrl(preview)} alt="" className="w-full" />
                {users.length > 0 && (
                  <span
                    className="absolute -right-1 -bottom-1 flex items-center rounded-full border-2 border-ink bg-panel px-1.5 text-xs font-bold text-chalk"
                    title={`Em uso: ${users.map((p) => p.nickname).join(', ')}`}
                  >
                    {users.length === 1 ? users[0].nickname.slice(0, 6) : `${users.length}×`}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        {notice && <p className="text-center text-sm text-red-300">{notice}</p>}
        <button onClick={onClose} className="btn-3d btn-dark rounded-xl py-3 font-semibold text-steel">
          Fechar
        </button>
      </div>
    </div>
  )
}

function SettingsSheet({ room, onUpdate, onClose }: SettingsSheetProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const [guide, setGuide] = useState<RoomSettings['mode'] | null>(null)
  const { settings } = room
  const { themes, theme_options: themeOptions } = settings
  const allThemes = themes.length === themeOptions.length

  useEffect(() => {
    if (guide) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, guide])

  const update = async (patch: UpdateSettingsRequest) => setNotice(await onUpdate(patch))
  const toggleTheme = (theme: string) => {
    if (themes.includes(theme) && themes.length === 1) {
      setNotice('Escolha pelo menos um tema.')
      return
    }
    update({ themes: themes.includes(theme) ? themes.filter((t) => t !== theme) : [...themes, theme] })
  }

  return (
    <>
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
              // Número ímpar de modos: o último ocupa a linha inteira.
              <div key={mode} className={`relative ${index === settings.mode_options.length - 1 && index % 2 === 0 ? 'col-span-2' : ''}`}>
                <button
                  onClick={() => update({ mode })}
                  aria-pressed={settings.mode === mode}
                  className={`btn-3d btn-sm flex h-full w-full flex-col gap-0.5 rounded-lg px-3 py-2 text-left ${
                    settings.mode === mode ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel hover:text-chalk'
                  }`}
                >
                  {/* Só o nome abre espaço para o i; a explicação usa a largura toda. */}
                  <span className="pr-5 font-semibold">{MODES[mode].name}</span>
                  <span className="text-xs leading-snug opacity-80">{MODES[mode].hint}</span>
                </button>
                <span className={`absolute top-1.5 right-1.5 ${settings.mode === mode ? 'text-ink' : 'text-steel'}`}>
                  <InfoButton onClick={() => setGuide(mode)} label={`Como funciona o ${MODES[mode].name}`} />
                </span>
              </div>
            ))}
          </div>
        </div>

        {settings.mode !== 'estimate' && <OptionRow
          title="Poderes"
          hint={POWERS_HINT[settings.mode]}
          options={[0, 1]}
          value={settings.powers ? 1 : 0}
          label={(n) => (n ? 'Com' : 'Sem')}
          onPick={(n) => update({ powers: n === 1 })}
        />}

        {settings.mode !== 'teams' && settings.mode !== 'estimate' && settings.powers && (
          <OptionRow
            title="Limite de poderes"
            hint="Quantos poderes cada um pode guardar ao mesmo tempo"
            options={settings.powerup_max_options}
            value={settings.powerup_max}
            label={(n) => String(n)}
            onPick={(powerup_max) => update({ powerup_max })}
          />
        )}

        {settings.mode === 'last_standing' && (
          <div className="flex flex-col gap-2">
            <h3 className="font-display text-xl tracking-wide">Perguntas</h3>
            <div className="grid grid-cols-2 gap-2">
              {settings.survival_kind_options.map((kind) => (
                <button
                  key={kind}
                  onClick={() => update({ survival_kind: kind })}
                  aria-pressed={settings.survival_kind === kind}
                  className={`btn-3d btn-sm flex flex-col gap-0.5 rounded-lg px-3 py-2 text-left ${
                    settings.survival_kind === kind ? 'btn-brand is-pressed text-ink' : 'btn-dark text-steel hover:text-chalk'
                  }`}
                >
                  <span className="font-semibold">{SURVIVAL_KINDS[kind].name}</span>
                  <span className="text-xs leading-snug opacity-80">{SURVIVAL_KINDS[kind].hint}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {settings.mode === 'teams' && (
          <>
            <OptionRow
              title="Times"
              hint="Cada time precisa de pelo menos 2 jogadores"
              options={settings.team_count_options}
              value={settings.team_count}
              label={(n) => String(n)}
              onPick={(team_count) => update({ team_count })}
            />
            <OptionRow
              title="Montagem"
              hint="O anfitrião monta tocando nos jogadores, ou sorteio no começo"
              options={[1, 0]}
              value={settings.team_pick === 'host' ? 1 : 0}
              label={(n) => (n ? 'Anfitrião' : 'Sorteio')}
              onPick={(n) => update({ team_pick: n ? 'host' : 'random' })}
            />
          </>
        )}

        {settings.mode === 'estimate' && (
          <OptionRow
            title="Perguntas"
            hint="20 segundos para cada chute"
            options={ESTIMATE_ROUNDS}
            value={estimateRounds(settings.rounds)}
            label={(n) => String(n)}
            onPick={(rounds) => update({ rounds })}
          />
        )}

        {settings.mode !== 'last_standing' && settings.mode !== 'hot_potato' && settings.mode !== 'estimate' && (
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
    {/* Fora do painel, para o toque no fundo do guia não fechar as configurações também. */}
    {guide && <ModeGuide mode={guide} onClose={() => setGuide(null)} />}
    </>
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

/** Times montados pelo anfitrião: os jogadores por time; o anfitrião toca num jogador para mudar de time. */
function TeamBuilder({
  room,
  playerId,
  isHost,
  onSetTeam,
  onNotice,
  onEditAvatar,
}: {
  room: RoomState
  playerId: string | null
  isHost: boolean
  onSetTeam: Props['onSetTeam']
  onNotice: (notice: string | null) => void
  onEditAvatar: () => void
}) {
  const { team_count: count, teams } = room.settings
  const move = async (player: PlayerView) => {
    playSound('select')
    onNotice(await onSetTeam(player.id, ((teams[player.id] ?? 0) + 1) % count))
  }
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }, (_, team) => {
        const members = room.players.filter((p) => teams[p.id] === team)
        return (
          <div key={team} className={`flex flex-col gap-1.5 rounded-xl p-2 ${TEAMS[team].bg}`}>
            <h3 className={`flex items-baseline justify-between px-1 font-display text-lg tracking-wide ${TEAMS[team].text}`}>
              {teamName(team)}
              <span className="font-sans text-sm">{members.length}</span>
            </h3>
            {members.length === 0 && <p className="px-1 text-sm text-steel">Ninguém ainda.</p>}
            {members.map((player) => (
              <button
                key={player.id}
                onClick={() => void move(player)}
                disabled={!isHost}
                className={`flex items-center gap-3 rounded-lg bg-panel px-3 py-1.5 text-left ${isHost ? 'btn-3d btn-sm btn-dark' : ''} ${player.connected ? '' : 'opacity-50'}`}
              >
                {player.id === playerId ? (
                  <MyAvatar player={player} className="size-9" onClick={onEditAvatar} />
                ) : (
                  <img src={avatarUrl(player)} alt="" className="size-9" />
                )}
                <span className="flex-1 truncate font-semibold">
                  {player.nickname}
                  {player.id === playerId && <span className="ml-2 text-sm font-normal text-steel">(você)</span>}
                </span>
                {player.id === room.host_id && <img src={coroa} alt="Anfitrião" title="Anfitrião" className="size-6" />}
                {isHost && <span className="text-xs text-steel">trocar ›</span>}
              </button>
            ))}
          </div>
        )
      })}
      {isHost && <p className="text-center text-sm text-steel">Toque num jogador para passar para o próximo time.</p>}
    </div>
  )
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
