import { useEffect, useState } from 'react'
import logo from './assets/logo.png'
import { Lobby } from './components/Lobby'
import { ProfileForm } from './components/ProfileForm'
import { loadSession, saveSession } from './lib/storage'
import { useRoom } from './lib/useRoom'

type Screen = { name: 'home' } | { name: 'create' } | { name: 'join'; code: string }

function codeFromUrl(): string | null {
  return window.location.pathname.match(/^\/sala\/([A-Za-z]{5})\/?$/)?.[1].toUpperCase() ?? null
}

// Um link para outra sala vale mais que a sessão salva de uma sala antiga.
const linkCode = codeFromUrl()
if (linkCode && loadSession()?.code !== linkCode) saveSession(null)

function setUrl(path: string) {
  if (window.location.pathname !== path) window.history.replaceState(null, '', path)
}

export default function App() {
  const { connected, rejoining, room, playerId, create, join, leave, start } = useRoom()
  const [screen, setScreen] = useState<Screen>(linkCode ? { name: 'join', code: linkCode } : { name: 'home' })

  useEffect(() => {
    if (room) setUrl(`/sala/${room.code}`)
    else if (screen.name !== 'join') setUrl('/')
  }, [room, screen.name])

  const leaveRoom = () => {
    leave()
    setScreen({ name: 'home' })
  }

  let content
  if (room) {
    content = <Lobby room={room} playerId={playerId} onLeave={leaveRoom} onStart={start} />
  } else if (rejoining) {
    content = <p className="font-hand text-xl text-steel">Voltando para a sala…</p>
  } else if (screen.name === 'home') {
    content = (
      <>
        <img src={logo} alt="Quem Sabe Menos?" className="w-full max-w-sm" />
        <div className="flex w-full flex-col gap-3">
          <button
            onClick={() => setScreen({ name: 'create' })}
            className="rounded-xl bg-brand py-4 font-display text-2xl tracking-wide text-ink"
          >
            Criar sala
          </button>
          <button
            onClick={() => setScreen({ name: 'join', code: '' })}
            className="rounded-xl bg-panel py-4 font-display text-2xl tracking-wide"
          >
            Entrar na sala
          </button>
        </div>
      </>
    )
  } else {
    content = (
      <ProfileForm
        key={screen.name}
        mode={screen.name}
        initialCode={screen.name === 'join' ? screen.code : undefined}
        disabled={!connected}
        onBack={() => setScreen({ name: 'home' })}
        onSubmit={(profile, code) => (screen.name === 'create' ? create(profile) : join(code, profile))}
      />
    )
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-8 px-4 py-10">
      {content}
      {!connected && <p className="font-hand text-lg text-steel">🔴 Conectando ao servidor…</p>}
    </main>
  )
}
