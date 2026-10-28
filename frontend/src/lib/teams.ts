/** Modo Times: nome e cores de cada time, pelo número dele (0 a 3). */
export const TEAMS = [
  { name: 'Burro', color: '#38BDF8', text: 'text-sky-300', bg: 'bg-sky-400/15', ring: 'ring-sky-400' },
  { name: 'Asno', color: '#F87171', text: 'text-red-300', bg: 'bg-red-400/15', ring: 'ring-red-400' },
  { name: 'Jegue', color: '#4ADE80', text: 'text-green-300', bg: 'bg-green-400/15', ring: 'ring-green-400' },
  { name: 'Mula', color: '#FACC15', text: 'text-yellow-200', bg: 'bg-yellow-300/15', ring: 'ring-yellow-300' },
]

export const teamName = (team: number) => `Time ${TEAMS[team].name}`
