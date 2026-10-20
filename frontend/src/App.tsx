import { useEffect, useState } from 'react'
import logo from './assets/logo.png'
import { socket } from './lib/socket'

function useServerLatency() {
  const [connected, setConnected] = useState(socket.connected)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)

  useEffect(() => {
    const measure = async () => {
      const start = performance.now()
      await socket.emitWithAck('ping_server')
      setLatencyMs(Math.round(performance.now() - start))
    }
    const onConnect = () => {
      setConnected(true)
      void measure()
    }
    const onDisconnect = () => setConnected(false)

    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    if (socket.connected) void measure()
    return () => {
      socket.off('connect', onConnect)
      socket.off('disconnect', onDisconnect)
    }
  }, [])

  return { connected, latencyMs }
}

export default function App() {
  const { connected, latencyMs } = useServerLatency()

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-8 px-4 py-10">
      <img src={logo} alt="Quem Sabe Menos?" className="w-full max-w-sm" />

      <div className="flex w-full flex-col gap-3">
        <button disabled className="rounded-xl bg-brand py-4 font-display text-2xl tracking-wide text-ink disabled:opacity-50">
          Criar sala
        </button>
        <button disabled className="rounded-xl bg-panel py-4 font-display text-2xl tracking-wide disabled:opacity-50">
          Entrar na sala
        </button>
      </div>

      <p className="font-hand text-lg text-steel">
        {connected ? `🟢 Servidor conectado${latencyMs !== null ? ` (${latencyMs} ms)` : ''}` : '🔴 Conectando ao servidor…'}
      </p>
    </main>
  )
}
