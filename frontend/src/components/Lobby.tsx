import { useState } from 'react'
import { AVATAR_URLS } from '../lib/avatars'
import type { RoomState } from '../types/events'

interface Props {
  room: RoomState
  playerId: string | null
  onLeave: () => void
  onStart: () => Promise<string | null>
  onSetRounds: (rounds: number) => Promise<string | null>
}

function inviteUrl(code: string) {
  return `${window.location.origin}/sala/${code}`
}

export function Lobby({ room, playerId, onLeave, onStart, onSetRounds }: Props) {
  const [notice, setNotice] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  const isHost = room.host_id === playerId
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

  const setRounds = async (rounds: number) => setNotice(await onSetRounds(rounds))

  return (
    <section className="flex w-full flex-col gap-6">
      <header className="flex flex-col items-center gap-3 rounded-2xl bg-panel p-5">
        <span className="text-sm font-semibold tracking-widest text-steel uppercase">Código da sala</span>
        <span className="font-display text-6xl tracking-[0.25em] text-brand">{room.code}</span>
        <button onClick={invite} className="rounded-xl bg-chalk px-5 py-2 font-semibold text-ink hover:bg-white">
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
              {!player.connected && <span className="font-hand text-steel">reconectando…</span>}
              {player.id === room.host_id && (
                <span title="Anfitrião" className="text-2xl">
                  👑
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="font-display text-2xl tracking-wide">Perguntas</h2>
        {isHost ? (
          <div className="grid grid-cols-6 gap-2">
            {room.settings.round_options.map((rounds) => (
              <button
                key={rounds}
                onClick={() => setRounds(rounds)}
                aria-pressed={room.settings.rounds === rounds}
                className={`rounded-lg py-2 font-semibold ${
                  room.settings.rounds === rounds ? 'bg-brand text-ink' : 'bg-panel text-steel hover:text-chalk'
                }`}
              >
                {rounds}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-steel">
            {room.settings.rounds} perguntas, {room.settings.answer_seconds} segundos cada
          </p>
        )}
      </div>

      {notice && <p className="text-center text-steel">{notice}</p>}

      {isHost ? (
        <div className="flex flex-col gap-2">
          <button
            onClick={start}
            disabled={!enoughPlayers || starting}
            className="rounded-xl bg-brand py-4 font-display text-2xl tracking-wide text-ink disabled:opacity-50"
          >
            Começar partida
          </button>
          {!enoughPlayers && (
            <p className="text-center font-hand text-lg text-steel">
              Precisa de pelo menos {room.min_players} jogadores. Chama a galera!
            </p>
          )}
        </div>
      ) : (
        <p className="text-center font-hand text-xl text-steel">Esperando o anfitrião começar…</p>
      )}

      <button onClick={onLeave} className="text-steel underline hover:text-chalk">
        Sair da sala
      </button>
    </section>
  )
}
