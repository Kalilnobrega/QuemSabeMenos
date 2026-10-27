import { useEffect, useState } from 'react'
import { Game } from './components/Game'
import { Lobby } from './components/Lobby'
import { Survival } from './components/Survival'
import { Logo } from './components/Logo'
import { ProfileForm } from './components/ProfileForm'
import { SoundToggle } from './components/SoundToggle'
import { loadSession, saveSession } from './lib/storage'
import { useRoom } from './lib/useRoom'

type Screen = { name: 'home' } | { name: 'create' } | { name: 'join'; code: string }

function codeFromUrl(): string | null {
  return window.location.pathname.match(/^\/sala\/([A-Za-z]{5})\/?$/)?.[1].toUpperCase() ?? null
}

// Um link para outra sala vale mais que a sessão salva de uma sala antiga.
const linkCode = codeFromUrl()
if (linkCode && loadSession()?.code !== linkCode) saveSession(null)

function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="currentColor" aria-hidden="true">
      <circle cx="9" cy="8" r="4" />
      <path d="M1.5 20c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5z" />
      <circle cx="17.5" cy="9" r="3" />
      <path d="M17 13.6c3.3 0 5.5 2.1 5.5 5.4H18.4c0-2.1-.6-3.9-1.9-5.3z" />
    </svg>
  )
}

function KeyIcon() {
  return (
    <svg viewBox="2.5 2.5 19 19" className="size-6" fill="currentColor" aria-hidden="true">
      <g transform="rotate(45 12 12)">
        <circle cx="5.5" cy="12" r="3.6" fill="none" stroke="currentColor" strokeWidth="2.6" />
        <rect x="9" y="10.6" width="13.5" height="2.8" rx="1" />
        <rect x="16" y="12.5" width="2.4" height="4.2" rx=".8" />
        <rect x="19.8" y="12.5" width="2.4" height="3.2" rx=".8" />
      </g>
    </svg>
  )
}

function setUrl(path: string) {
  if (window.location.pathname !== path) window.history.replaceState(null, '', path)
}

export default function App() {
  const { connected, rejoining, snapshot, playerId, create, join, leave, start, playAgain, answer, bet, duelBet, armPowerUp, usePowerUp, skipResults, updateSettings } = useRoom()
  const room = snapshot?.room ?? null
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
  if (snapshot && room?.survival) {
    content = <Survival snapshot={snapshot} playerId={playerId} onAnswer={answer} onArm={armPowerUp} onUse={usePowerUp} onSkip={skipResults} onPlayAgain={playAgain} onLeave={leaveRoom} />
  } else if (snapshot && room?.game) {
    content = <Game snapshot={snapshot} playerId={playerId} onAnswer={answer} onBet={bet} onDuelBet={duelBet} onArm={armPowerUp} onUse={usePowerUp} onSkip={skipResults} onPlayAgain={playAgain} onLeave={leaveRoom} />
  } else if (room) {
    content = <Lobby room={room} playerId={playerId} onLeave={leaveRoom} onStart={start} onUpdateSettings={updateSettings} />
  } else if (rejoining) {
    content = <p className="font-hand font-medium text-lg text-steel">Voltando para a sala…</p>
  } else if (screen.name === 'home') {
    content = (
      <>
        <Logo className="w-full max-w-sm" />
        <div className="flex w-full flex-col gap-3">
          <button
            onClick={() => setScreen({ name: 'create' })}
            className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink"
          >
            <span className="flex items-center justify-center gap-3">
              <UsersIcon />
              Criar sala
            </span>
          </button>
          <button
            onClick={() => setScreen({ name: 'join', code: '' })}
            className="btn-3d btn-dark rounded-xl py-4 font-display text-2xl tracking-wide"
          >
            <span className="flex items-center justify-center gap-3">
              <KeyIcon />
              Entrar na sala
            </span>
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
    // Na partida o conteúdo fica alinhado ao topo: centralizado, qualquer mudança de altura empurraria a tela.
    <main
      className={`mx-auto flex min-h-dvh max-w-md flex-col items-center gap-8 px-4 ${
        room?.game || room?.survival ? 'justify-start pt-6 pb-10' : 'justify-center py-10'
      }`}
    >
      {content}
      <SoundToggle />
      {!connected && (
        <p className="flex items-center gap-2 font-hand font-medium text-base text-steel">
          <span className="relative flex size-2.5" aria-hidden="true">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex size-2.5 rounded-full bg-red-500" />
          </span>
          Conectando ao servidor…
        </p>
      )}
    </main>
  )
}
