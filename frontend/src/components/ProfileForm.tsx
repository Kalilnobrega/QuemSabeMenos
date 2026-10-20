import { useState, type FormEvent } from 'react'
import { AVATAR_NAMES, AVATAR_URLS, AVATARS, randomAvatar } from '../lib/avatars'
import { loadProfile, type Profile } from '../lib/storage'

const CODE_LENGTH = 5
const NICKNAME_MAX_LENGTH = 16

interface Props {
  mode: 'create' | 'join'
  initialCode?: string
  disabled: boolean
  onBack: () => void
  onSubmit: (profile: Profile, code: string) => Promise<string | null>
}

export function ProfileForm({ mode, initialCode = '', disabled, onBack, onSubmit }: Props) {
  const [code, setCode] = useState(initialCode)
  const [profile, setProfile] = useState<Profile>(() => loadProfile() ?? { nickname: '', avatar: randomAvatar() })
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const nickname = profile.nickname.trim()
  const ready = nickname.length > 0 && (mode === 'create' || code.length === CODE_LENGTH)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!ready || sending) return
    setSending(true)
    setError(await onSubmit({ ...profile, nickname }, code))
    setSending(false)
  }

  return (
    <form onSubmit={submit} className="flex w-full flex-col gap-6">
      <header className="flex items-center gap-3">
        <button type="button" onClick={onBack} aria-label="Voltar" className="rounded-lg px-2 py-1 text-2xl text-steel hover:text-chalk">
          ←
        </button>
        <h1 className="font-display text-4xl tracking-wide text-brand">{mode === 'create' ? 'Criar sala' : 'Entrar na sala'}</h1>
      </header>

      {mode === 'join' && (
        <label className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-steel">Código da sala</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, CODE_LENGTH))}
            placeholder="ABCDE"
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck={false}
            className="rounded-xl bg-panel px-4 py-3 text-center font-display text-4xl tracking-[0.3em] text-brand placeholder:text-steel/40 focus:outline-2 focus:outline-brand"
          />
        </label>
      )}

      <label className="flex flex-col gap-2">
        <span className="text-sm font-semibold text-steel">Seu apelido</span>
        <input
          value={profile.nickname}
          onChange={(e) => setProfile({ ...profile, nickname: e.target.value })}
          maxLength={NICKNAME_MAX_LENGTH}
          placeholder="Como a galera vai te chamar"
          autoComplete="nickname"
          className="rounded-xl bg-panel px-4 py-3 text-lg placeholder:text-steel focus:outline-2 focus:outline-brand"
        />
      </label>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-semibold text-steel">Escolha seu bicho</legend>
        <div className="grid grid-cols-4 gap-3">
          {AVATARS.map((avatar) => {
            const selected = profile.avatar === avatar
            return (
              <button
                key={avatar}
                type="button"
                onClick={() => setProfile({ ...profile, avatar })}
                aria-label={AVATAR_NAMES[avatar]}
                aria-pressed={selected}
                className={`rounded-full p-1 transition ${selected ? 'scale-105 ring-4 ring-brand' : 'opacity-70 hover:opacity-100'}`}
              >
                <img src={AVATAR_URLS[avatar]} alt="" className="w-full" />
              </button>
            )
          })}
        </div>
      </fieldset>

      {error && <p className="rounded-xl bg-red-500/15 px-4 py-3 text-center text-red-300">{error}</p>}

      <button
        type="submit"
        disabled={!ready || sending || disabled}
        className="rounded-xl bg-brand py-4 font-display text-2xl tracking-wide text-ink disabled:opacity-50"
      >
        {sending ? 'Só um instante…' : mode === 'create' ? 'Criar sala' : 'Entrar'}
      </button>
    </form>
  )
}
