import type { Avatar } from './avatars'

// localStorage pode falhar (aba anônima, bloqueio de site): tudo aqui é "melhor esforço".

export interface Session {
  code: string
  token: string
}

export interface Profile {
  nickname: string
  avatar: Avatar
}

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function write(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // sem persistência: o jogador só não reconecta sozinho após recarregar
  }
}

export const loadSession = () => read<Session>('qsm:session')
export const saveSession = (session: Session | null) => write('qsm:session', session)

export const loadProfile = () => read<Profile>('qsm:profile')
export const saveProfile = (profile: Profile) => write('qsm:profile', profile)
