import { useCallback, useEffect, useState } from 'react'
import type { ErrorAck, JoinedAck, OkAck, RoomState } from '../types/events'
import { socket } from './socket'
import { loadSession, saveProfile, saveSession, type Profile } from './storage'

const ACK_TIMEOUT_MS = 5000

async function call<T>(event: string, data?: unknown): Promise<T | ErrorAck> {
  try {
    const timed = socket.timeout(ACK_TIMEOUT_MS)
    return data === undefined ? await timed.emitWithAck(event) : await timed.emitWithAck(event, data)
  } catch {
    return { ok: false, error: 'O servidor não respondeu. Tente de novo.' }
  }
}

/** Estado da sala do jogador e as ações do lobby. Reentra sozinho na sala ao reconectar. */
export function useRoom() {
  const [connected, setConnected] = useState(socket.connected)
  const [room, setRoom] = useState<RoomState | null>(null)
  const [playerId, setPlayerId] = useState<string | null>(null)
  const [rejoining, setRejoining] = useState(() => loadSession() !== null)

  const enter = useCallback((ack: JoinedAck) => {
    saveSession({ code: ack.room.code, token: ack.token })
    setPlayerId(ack.player_id)
    setRoom(ack.room)
  }, [])

  useEffect(() => {
    const rejoin = async () => {
      const session = loadSession()
      if (!session) return setRejoining(false)
      const ack = await call<JoinedAck>('rejoin_room', session)
      if (ack.ok) {
        enter(ack)
      } else {
        saveSession(null)
        setRoom(null)
      }
      setRejoining(false)
    }
    const onConnect = () => {
      setConnected(true)
      void rejoin()
    }
    const onDisconnect = () => setConnected(false)

    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('room_state', setRoom)
    if (socket.connected) void rejoin()
    return () => {
      socket.off('connect', onConnect)
      socket.off('disconnect', onDisconnect)
      socket.off('room_state', setRoom)
    }
  }, [enter])

  const joinWith = useCallback(
    async (event: 'create_room' | 'join_room', profile: Profile, code?: string) => {
      saveProfile(profile)
      const ack = await call<JoinedAck>(event, code ? { ...profile, code } : profile)
      if (!ack.ok) return ack.error
      enter(ack)
      return null
    },
    [enter],
  )

  const create = useCallback((profile: Profile) => joinWith('create_room', profile), [joinWith])
  const join = useCallback((code: string, profile: Profile) => joinWith('join_room', profile, code), [joinWith])

  const leave = useCallback(() => {
    saveSession(null)
    setRoom(null)
    setPlayerId(null)
    void call<OkAck>('leave_room')
  }, [])

  const start = useCallback(async () => {
    const ack = await call<OkAck>('start_game')
    return ack.ok ? null : ack.error
  }, [])

  return { connected, rejoining, room, playerId, create, join, leave, start }
}
