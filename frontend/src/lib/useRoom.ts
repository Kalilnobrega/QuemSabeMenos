import { useCallback, useEffect, useState } from 'react'
import type { ArmPowerUpRequest, ErrorAck, JoinedAck, OkAck, RoomState, UpdateSettingsRequest } from '../types/events'
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

export interface Snapshot {
  room: RoomState
  /** performance.now() de quando o estado chegou; os prazos do jogo são relativos a ele. */
  receivedAt: number
}

/** Envia um comando e devolve a mensagem de erro, ou null se deu certo. */
async function request(event: string, data?: unknown): Promise<string | null> {
  const ack = await call<OkAck>(event, data)
  return ack.ok ? null : ack.error
}

/** Estado da sala do jogador e as ações do lobby e da partida. Reentra sozinho na sala ao reconectar. */
export function useRoom() {
  const [connected, setConnected] = useState(socket.connected)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [playerId, setPlayerId] = useState<string | null>(null)
  const [rejoining, setRejoining] = useState(() => loadSession() !== null)

  const setRoom = useCallback((room: RoomState | null) => {
    setSnapshot(room ? { room, receivedAt: performance.now() } : null)
  }, [])

  const enter = useCallback(
    (ack: JoinedAck) => {
      saveSession({ code: ack.room.code, token: ack.token })
      setPlayerId(ack.player_id)
      setRoom(ack.room)
    },
    [setRoom],
  )

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
  }, [enter, setRoom])

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
  }, [setRoom])

  const start = useCallback(() => request('start_game'), [])
  const playAgain = useCallback(() => request('play_again'), [])
  const answer = useCallback(
    (option: number, team: number | null = null, potato: number | null = null) => request('submit_answer', { option, team, potato }),
    [],
  )
  const bet = useCallback((amount: number) => request('submit_bet', { amount }), [])
  const duelBet = useCallback((choice: string) => request('submit_duel_bet', { choice }), [])
  const armPowerUp = useCallback(
    (kind: ArmPowerUpRequest['kind'], target: string | null, legendary = false, theme: string | null = null, targetTeam: number | null = null) =>
      request('arm_powerup', { kind, target, legendary, theme, target_team: targetTeam }),
    [],
  )
  const usePowerUp = useCallback(
    (kind: ArmPowerUpRequest['kind'], targetTeam: number | null = null, potato: number | null = null) =>
      request('use_powerup', { kind, target_team: targetTeam, potato }),
    [],
  )
  const skipResults = useCallback(() => request('skip_results'), [])
  const updateSettings = useCallback((patch: UpdateSettingsRequest) => request('update_settings', patch), [])
  const chooseRepresentative = useCallback((choice: string) => request('choose_representative', { choice }), [])
  const setTeam = useCallback((player_id: string, team: number) => request('set_team', { player_id, team }), [])

  return { connected, rejoining, snapshot, playerId, create, join, leave, start, playAgain, answer, bet, duelBet, armPowerUp, usePowerUp, skipResults, updateSettings, setTeam, chooseRepresentative }
}
