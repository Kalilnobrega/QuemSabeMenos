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
