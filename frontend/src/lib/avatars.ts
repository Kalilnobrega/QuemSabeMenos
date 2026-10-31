import type { PlayerView } from '../types/events'

export type Avatar = PlayerView['avatar']

const urls = import.meta.glob<string>('../assets/avatars/*.svg', { eager: true, query: '?url', import: 'default' })

export const AVATAR_URLS = Object.fromEntries(
  Object.entries(urls).map(([path, url]) => [path.split('/').pop()!.replace('.svg', ''), url]),
) as Record<Avatar, string>

export const AVATARS = Object.keys(AVATAR_URLS) as Avatar[]

export const AVATAR_NAMES: Record<Avatar, string> = {
  burro: 'Burro',
  cachorro: 'Cachorro',
  coelho: 'Coelho',
  coruja: 'Coruja',
  galinha: 'Galinha',
  gato: 'Gato',
  leao: 'Leão',
  macaco: 'Macaco',
  ovelha: 'Ovelha',
  panda: 'Panda',
  pinguim: 'Pinguim',
  porco: 'Porco',
  raposa: 'Raposa',
  sapo: 'Sapo',
  urso: 'Urso',
  vaca: 'Vaca',
}

export function randomAvatar(): Avatar {
  return AVATARS[Math.floor(Math.random() * AVATARS.length)]
}

// Bicho repetido na sala: o disco de fundo muda de cor (o primeiro fica com o amarelo de sempre).
const raw = import.meta.glob<string>('../assets/avatars/*.svg', { eager: true, query: '?raw', import: 'default' })
const SVGS = Object.fromEntries(Object.entries(raw).map(([path, svg]) => [path.split('/').pop()!.replace('.svg', ''), svg])) as Record<Avatar, string>
const DISC = 'r="61" fill="#FFC107"'
export const VARIANT_COLORS = ['#60A5FA', '#F472B6', '#4ADE80', '#C084FC', '#FB923C', '#2DD4BF', '#F87171', '#A3E635', '#E5E7EB', '#38BDF8', '#FDA4AF']
const variantUrls = new Map<string, string>()

/** A imagem do bicho de um jogador, já com a cor de fundo da variante quando ele repete o bicho de alguém. */
export function avatarUrl(player: { avatar: Avatar; avatar_variant?: number }) {
  const variant = player.avatar_variant ?? 0
  if (variant <= 0) return AVATAR_URLS[player.avatar]
  const key = `${player.avatar}:${variant}`
  let url = variantUrls.get(key)
  if (!url) {
    const color = VARIANT_COLORS[(variant - 1) % VARIANT_COLORS.length]
    url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(SVGS[player.avatar].replace(DISC, `r="61" fill="${color}"`))}`
    variantUrls.set(key, url)
  }
  return url
}
