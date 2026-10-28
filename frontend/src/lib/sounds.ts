/**
 * Sons do jogo, sintetizados na hora com a Web Audio API (nenhum arquivo para baixar).
 *
 * Para tirar um som do jogo, troque `true` por `false` em SOUND_ENABLED.
 * O botão de som da tela liga e desliga tudo, e a escolha fica salva no aparelho.
 */

export const SOUND_ENABLED = {
  join: true,
  leave: true,
  start: true,
  slam: true,
  countTick: true,
  countGo: true,
  levelHop: true,
  levelUp: true,
  impossible: true,
  typing: true,
  answersOpen: true,
  select: true,
  urgentTick: true,
  timeUp: true,
  correct: true,
  wrong: true,
  noAnswer: true,
  countUp: true,
  streakFire: false, // fora por enquanto
  streakIce: false, // fora por enquanto
  perfectEasy: true,
  rankingSwish: true,
  flashbang: true,
  potatoBoom: true,
  daggerThrow: true,
  daggerHit: true,
  podiumWinner: true,
  podiumLoser: true,
  skip: true,
  powerArm: true,
  powerHit: true,
  shield: true,
  theme: true,
  investment: true,
  backpack: true,
  resurrection: true,
  duelIntro: true,
  duelFight: true,
  duelLastQuestion: true,
  duelBet: true,
  duelWin: true,
  duelLose: true,
  duelWatch: true,
}

export type SoundId = keyof typeof SOUND_ENABLED

/** Onde e quando cada som toca (mostrado também na página de escolha dos sons). */
export const SOUND_INFO: Record<SoundId, { name: string; moment: string; group: string }> = {
  join: { group: 'Lobby', name: 'Pop subindo', moment: 'Alguém entra na sala' },
  leave: { group: 'Lobby', name: 'Pop descendo', moment: 'Alguém sai da sala' },
  start: { group: 'Transições', name: 'Whoosh de arrancada', moment: 'A partida começa (tela "Prepare-se!")' },
  slam: { group: 'Transições', name: 'Carimbo (fiu… TUM!)', moment: 'O título "Prepare-se!" bate na tela' },
  countTick: { group: 'Transições', name: 'Tic da contagem', moment: 'Contagem 3 e 2, na abertura e antes da impossível' },
  countGo: { group: 'Transições', name: 'Bipe de largada (piii!)', moment: 'Contagem chega no 1, como o último sinal de uma largada' },
  levelHop: { group: 'Transições', name: 'Fiu do pulo e tum do pouso', moment: 'O destaque pula de um nível para o outro na trilha' },
  levelUp: { group: 'Transições', name: 'Acorde subindo', moment: 'O nome do novo nível aparece (Média, Difícil)' },
  impossible: { group: 'Transições', name: 'Chama e tambor grave', moment: 'Tela da pergunta impossível' },
  typing: { group: 'Pergunta', name: 'Tec-tec de máquina de escrever', moment: 'Enquanto o texto da pergunta aparece' },
  answersOpen: { group: 'Pergunta', name: 'Trava abrindo (tchk-uup)', moment: 'As alternativas são liberadas' },
  select: { group: 'Pergunta', name: 'Blip de bolha', moment: 'Você toca numa alternativa' },
  urgentTick: { group: 'Pergunta', name: 'Tique-taque acelerando', moment: 'Últimos 3 segundos, se você ainda não respondeu' },
  timeUp: { group: 'Pergunta', name: 'Despertador de tempo esgotado', moment: 'O tempo acaba e você não respondeu' },
  correct: { group: 'Revelação', name: 'Plim de moedinha', moment: 'Você acertou' },
  wrong: { group: 'Revelação', name: 'Fon-fon de buzina boba', moment: 'Você errou' },
  noAnswer: { group: 'Revelação', name: 'Grilos', moment: 'Você não respondeu' },
  countUp: { group: 'Revelação', name: 'Trrr de contador', moment: 'O seu QI sobe ou desce no placar' },
  streakFire: { group: 'Revelação', name: 'Fwoosh de fogo', moment: 'Alguém faz uma sequência de acertos' },
  streakIce: { group: 'Revelação', name: 'Gelo rachando', moment: 'Alguém faz uma sequência de erros' },
  perfectEasy: { group: 'Revelação', name: 'Brilho de estrela', moment: 'Alguém gabarita as fáceis' },
  flashbang: { group: 'Pergunta', name: 'Estouro e zumbido', moment: 'A Flashbang estoura em você' },
  daggerThrow: { group: 'Habilidades', name: 'Assobio de lâmina girando', moment: 'A Adaga é arremessada' },
  daggerHit: { group: 'Habilidades', name: 'Batida seca e corte', moment: 'A Adaga crava no alvo' },
  potatoBoom: { group: 'Batata quente', name: 'Chiado, BUM, cacos caindo e zumbido', moment: 'A batata explode na mão de alguém' },
  rankingSwish: { group: 'Revelação', name: 'Swish', moment: 'As posições do ranking mudam' },
  podiumWinner: { group: 'Pódio', name: 'Fanfarra de vitória', moment: 'O pódio aparece, com o vencedor' },
  podiumLoser: { group: 'Pódio', name: 'Trombone triste (uá-uá-uá)', moment: 'Logo depois, para quem sabe menos' },
  skip: { group: 'Revelação', name: 'Pulinho para a frente', moment: 'Você toca em Pular' },
  powerArm: { group: 'Habilidades', name: 'Trava e acorde', moment: 'Você arma ou usa uma habilidade' },
  powerHit: { group: 'Habilidades', name: 'Ops (dois tons caindo)', moment: 'Uma sabotagem começa a valer em você' },
  shield: { group: 'Habilidades', name: 'Batida de metal (gravado)', moment: 'O Escudo segura um erro seu' },
  theme: { group: 'Habilidades', name: 'Baralho abrindo (gravado)', moment: 'Você escolhe o tema' },
  investment: { group: 'Habilidades', name: 'Moedas na mão (gravado)', moment: 'Bônus do Investimento' },
  backpack: { group: 'Habilidades', name: 'Zíper (gravado)', moment: 'Você abre a Mochila' },
  resurrection: { group: 'Habilidades', name: 'Coral de anjos (gravado)', moment: 'Alguém usa a Ressurreição' },
  duelIntro: { group: 'X1', name: 'Choque de espadas (gravado)', moment: 'Entrada do X1' },
  duelFight: { group: 'X1', name: '"Fight!" (gravado)', moment: 'O duelo começa' },
  duelLastQuestion: { group: 'X1', name: '"Final round" (gravado)', moment: 'Última pergunta do X1' },
  duelBet: { group: 'X1', name: 'Fichas (gravado)', moment: 'Você aposta no X1' },
  duelWin: { group: 'X1', name: '"You win!" (gravado)', moment: 'Você vence o X1' },
  duelLose: { group: 'X1', name: '"Game over" (gravado)', moment: 'Você perde o X1' },
  duelWatch: { group: 'X1', name: '"Winner" (gravado)', moment: 'Fim do X1, para quem assistiu' },
}

// Sons gravados (Kenney e OpenGameArt em CC0; o coral é do Pixabay, que não pede crédito). Já vêm no
// mesmo volume dos sintetizados e tocam pelo mesmo volume geral.
const FILE_URLS = import.meta.glob<string>('../assets/sounds/*.m4a', { eager: true, query: '?url', import: 'default' })
const fileUrl = (id: string) => FILE_URLS[`../assets/sounds/${id}.m4a`]
const buffers = new Map<string, Promise<AudioBuffer | null>>()

function load(id: string) {
  let buffer = buffers.get(id)
  if (!buffer) {
    const { c } = audio()
    buffer = fetch(fileUrl(id))
      .then((r) => r.arrayBuffer())
      .then((data) => c.decodeAudioData(data))
      .catch(() => null)
    buffers.set(id, buffer)
  }
  return buffer
}

/** Toca um som gravado; o primeiro de cada um pode atrasar um pouco enquanto carrega. */
function file(id: string, at = 0) {
  const started = audio().c.currentTime
  void load(id).then((buffer) => {
    if (!buffer) return
    const { c, out } = audio()
    const src = c.createBufferSource()
    src.buffer = buffer
    src.connect(out)
    src.start(Math.max(c.currentTime, started + at))
  })
}

const VOLUME = 0.5
const MUTE_KEY = 'qsm-sound-muted'

let ctx: AudioContext | null = null
let master: GainNode | null = null
let noiseBuffer: AudioBuffer | null = null

function audio() {
  if (!ctx) {
    ctx = new AudioContext()
    master = ctx.createGain()
    master.gain.value = VOLUME
    master.connect(ctx.destination)
  }
  if (ctx.state === 'suspended') void ctx.resume()
  return { c: ctx, out: master! }
}

interface ToneOptions {
  at?: number
  dur?: number
  type?: OscillatorType
  gain?: number
  to?: number
  attack?: number
  lowpass?: number
  vibrato?: number
}

function tone(freq: number, { at = 0, dur = 0.15, type = 'sine', gain = 0.3, to, attack = 0.005, lowpass, vibrato }: ToneOptions = {}) {
  const { c, out } = audio()
  const t = c.currentTime + at
  const osc = c.createOscillator()
  const env = c.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t)
  if (to) osc.frequency.exponentialRampToValueAtTime(to, t + dur)
  if (vibrato) {
    const lfo = c.createOscillator()
    const depth = c.createGain()
    lfo.frequency.value = 6
    depth.gain.value = vibrato
    lfo.connect(depth).connect(osc.frequency)
    lfo.start(t)
    lfo.stop(t + dur + 0.05)
  }
  env.gain.setValueAtTime(0.0001, t)
  env.gain.exponentialRampToValueAtTime(gain, t + attack)
  env.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  let node: AudioNode = osc.connect(env)
  if (lowpass) {
    const filter = c.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = lowpass
    node = node.connect(filter)
  }
  node.connect(out)
  osc.start(t)
  osc.stop(t + dur + 0.05)
}

interface NoiseOptions {
  at?: number
  dur?: number
  gain?: number
  filter?: BiquadFilterType
  freq?: number
  to?: number
  q?: number
}

function noise({ at = 0, dur = 0.3, gain = 0.2, filter = 'bandpass', freq = 1000, to, q = 1 }: NoiseOptions = {}) {
  const { c, out } = audio()
  if (!noiseBuffer) {
    noiseBuffer = c.createBuffer(1, c.sampleRate * 2, c.sampleRate)
    const data = noiseBuffer.getChannelData(0)
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
  }
  const t = c.currentTime + at
  const src = c.createBufferSource()
  src.buffer = noiseBuffer
  const biquad = c.createBiquadFilter()
  biquad.type = filter
  biquad.Q.value = q
  biquad.frequency.setValueAtTime(freq, t)
  if (to) biquad.frequency.exponentialRampToValueAtTime(to, t + dur)
  const env = c.createGain()
  env.gain.setValueAtTime(0.0001, t)
  env.gain.exponentialRampToValueAtTime(gain, t + Math.min(0.05, dur / 3))
  env.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  src.connect(biquad).connect(env).connect(out)
  src.start(t)
  src.stop(t + dur + 0.05)
}

/** Momentos em que um número contando com easeInOut passa por k/n (para o "trrr" acompanhar o placar). */
function easedTicks(n: number) {
  const ease = (k: number) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2)
  return Array.from({ length: n }, (_, i) => {
    let lo = 0
    let hi = 1
    for (let step = 0; step < 20; step++) {
      const mid = (lo + hi) / 2
      if (ease(mid) < (i + 1) / n) lo = mid
      else hi = mid
    }
    return hi
  })
}

const NOTE = { C5: 523.25, E5: 659.25, G5: 783.99, C6: 1046.5, G4: 392 }

const SYNTHS: Record<SoundId, (arg?: number) => void> = {
  join: () => {
    tone(520, { dur: 0.09, to: 880, gain: 0.25 })
    tone(880, { at: 0.07, dur: 0.1, to: 1250, gain: 0.15 })
  },
  leave: () => tone(700, { dur: 0.18, to: 330, gain: 0.2 }),
  start: () => noise({ dur: 0.6, freq: 300, to: 3200, q: 0.8, gain: 0.25 }),
  // O título cai na tela como um carimbo: um "fiu" descendo e o "TUM" da batida (aos 0,15 s).
  slam: () => {
    noise({ dur: 0.15, freq: 3000, to: 500, q: 1.2, gain: 0.12 })
    tone(115, { at: 0.15, dur: 0.35, to: 48, gain: 0.7 })
    noise({ at: 0.15, dur: 0.12, filter: 'lowpass', freq: 900, gain: 0.3 })
  },
  countTick: () => tone(1100, { dur: 0.06, type: 'square', gain: 0.07 }),
  // Último bipe de uma largada: da mesma família do tic do 3 e do 2, só que mais agudo e longo.
  countGo: () => tone(1650, { dur: 0.45, type: 'square', gain: 0.08, attack: 0.003 }),
  // Pulo de desenho animado: um "fiu" subindo no salto e um "tum" no pouso.
  levelHop: () => {
    tone(500, { dur: 0.28, to: 1400, gain: 0.12 })
    noise({ dur: 0.25, freq: 800, to: 3000, q: 2, gain: 0.08 })
    tone(150, { at: 0.3, dur: 0.15, to: 70, gain: 0.45 })
    tone(700, { at: 0.3, dur: 0.06, type: 'triangle', gain: 0.08 })
  },
  levelUp: () => {
    ;[NOTE.C5, NOTE.E5, NOTE.G5, NOTE.C6].forEach((f, i) => tone(f, { at: i * 0.08, dur: 0.3, type: 'triangle', gain: 0.15 }))
  },
  impossible: () => file('impossible'),
  typing: () => noise({ dur: 0.025, filter: 'highpass', freq: 3500, gain: 0.04 }),
  // As respostas destravam: o "tchk" de uma trava abrindo e um "uup" subindo, de "pode responder!".
  answersOpen: () => {
    noise({ dur: 0.03, freq: 2200, q: 3, gain: 0.25 })
    noise({ at: 0.05, dur: 0.03, freq: 1600, q: 3, gain: 0.2 })
    tone(420, { at: 0.08, dur: 0.16, to: 840, gain: 0.16 })
  },
  // "Blip" de bolha, mais macio que um clique seco.
  select: () => tone(600, { dur: 0.08, to: 950, gain: 0.22 }),
  // arg: segundos que faltam (3, 2 ou 1); o tique-taque acelera perto do fim.
  urgentTick: (secondsLeft = 3) => {
    const ticks = secondsLeft >= 3 ? 1 : secondsLeft === 2 ? 2 : 4
    for (let i = 0; i < ticks; i++) tone(i % 2 ? 950 : 1250, { at: i / ticks, dur: 0.06, type: 'square', gain: 0.07 })
  },
  // Despertador tocando rapidinho: o tempo acabou.
  timeUp: () => {
    for (let i = 0; i < 8; i++) tone(i % 2 ? 1250 : 1500, { at: i * 0.055, dur: 0.045, type: 'square', gain: 0.05 })
  },
  correct: () => {
    tone(988, { dur: 0.09, type: 'square', gain: 0.09 })
    tone(1319, { at: 0.08, dur: 0.4, type: 'square', gain: 0.09 })
  },
  wrong: () => {
    tone(230, { dur: 0.18, type: 'sawtooth', gain: 0.18, lowpass: 1500 })
    tone(180, { at: 0.22, dur: 0.35, type: 'sawtooth', gain: 0.18, lowpass: 1500 })
  },
  noAnswer: () => {
    ;[0, 0.07, 0.14, 0.5, 0.57, 0.64].forEach((at) => tone(4300, { at, dur: 0.04, gain: 0.04 }))
  },
  // arg: quanto o QI mudou; sobe o tom quando ganha e desce quando perde.
  countUp: (delta = 1) => {
    const up = delta >= 0
    easedTicks(18).forEach((k, i) =>
      tone(up ? 1400 + i * 25 : 1400 - i * 25, { at: 0.4 + 1.8 * k, dur: 0.02, type: 'square', gain: 0.035 }),
    )
  },
  // Fogo acendendo: um "vush" grave, o chiado da chama e estalos de lenha.
  streakFire: () => {
    tone(90, { dur: 0.35, to: 160, gain: 0.35 })
    noise({ dur: 0.9, freq: 600, to: 2200, q: 0.6, gain: 0.22 })
    ;[0.15, 0.27, 0.34, 0.5, 0.62, 0.78].forEach((at) => noise({ at, dur: 0.02, filter: 'highpass', freq: 3000, gain: 0.18 }))
  },
  // Congelando: estalo de gelo e um brilho de cristal descendo, bem gelado.
  streakIce: () => {
    noise({ dur: 0.06, filter: 'highpass', freq: 2500, gain: 0.3 })
    ;[3136, 2637, 2349, 1976, 1568].forEach((f, i) => tone(f, { at: 0.05 + i * 0.07, dur: 0.35, gain: 0.06 }))
    noise({ at: 0.05, dur: 0.6, filter: 'highpass', freq: 7000, gain: 0.05 })
  },
  perfectEasy: () => {
    ;[1568, 2093, 2637, 3136].forEach((f, i) => tone(f, { at: i * 0.06, dur: 0.25, gain: 0.07 }))
  },
  flashbang: () => {
    noise({ dur: 0.45, filter: 'lowpass', freq: 3000, to: 400, gain: 0.7 })
    tone(90, { dur: 0.35, to: 35, gain: 0.7 })
    tone(3800, { at: 0.2, dur: 2.8, gain: 0.035 })
  },
  daggerThrow: () => {
    // A lâmina girando no ar: três assobios rápidos subindo.
    ;[0, 0.14, 0.28].forEach((at, i) => noise({ at, dur: 0.14, freq: 1800 + i * 600, to: 5200 + i * 600, q: 6, gain: 0.12 }))
  },
  daggerHit: () => {
    noise({ dur: 0.08, filter: 'highpass', freq: 3000, gain: 0.35 })
    tone(140, { dur: 0.22, to: 55, gain: 0.6 })
    noise({ at: 0.03, dur: 0.25, filter: 'lowpass', freq: 900, to: 200, gain: 0.35 })
  },
  potatoBoom: () => {
    // Pavio chiando no fim, o estouro grave que vai abafando, os pedaços caindo e o zumbido da
    // Flashbang no ouvido.
    noise({ dur: 0.18, filter: 'highpass', freq: 4000, to: 7000, gain: 0.08 })
    tone(3800, { at: 0.36, dur: 2.8, gain: 0.035 })
    noise({ at: 0.16, dur: 1.4, filter: 'lowpass', freq: 2400, to: 90, gain: 0.85 })
    tone(110, { at: 0.16, dur: 0.6, to: 28, gain: 0.8 })
    tone(55, { at: 0.18, dur: 0.9, to: 22, type: 'triangle', gain: 0.5 })
    ;[0.42, 0.5, 0.61, 0.69, 0.83, 0.97, 1.12].forEach((at, i) =>
      noise({ at, dur: 0.03, freq: 1800 + (i % 3) * 900, q: 4, gain: 0.14 - i * 0.012 }),
    )
  },
  rankingSwish: () => noise({ dur: 0.35, freq: 2500, to: 600, q: 1.5, gain: 0.12 }),
  podiumWinner: () => {
    const notes: [number, number, number][] = [
      [NOTE.G4, 0, 0.12],
      [NOTE.C5, 0.13, 0.12],
      [NOTE.E5, 0.26, 0.12],
      [NOTE.G5, 0.39, 0.22],
      [NOTE.E5, 0.62, 0.12],
      [NOTE.G5, 0.75, 0.7],
    ]
    for (const [f, at, dur] of notes) {
      tone(f, { at, dur, type: 'sawtooth', gain: 0.07, lowpass: 2500 })
      tone(f * 1.005, { at, dur, type: 'square', gain: 0.04, lowpass: 2500 })
    }
  },
  podiumLoser: () => {
    ;[293.66, 277.18, 261.63].forEach((f, i) => tone(f, { at: i * 0.45, dur: 0.4, type: 'sawtooth', gain: 0.14, lowpass: 900 }))
    tone(246.94, { at: 1.35, dur: 1.2, type: 'sawtooth', gain: 0.14, lowpass: 900, vibrato: 6 })
  },  // Pulinho para a frente: um sopro rápido e dois degraus subindo.
  skip: () => {
    noise({ dur: 0.18, freq: 700, to: 3200, q: 1.4, gain: 0.12 })
    tone(520, { dur: 0.07, to: 780, type: 'triangle', gain: 0.13 })
    tone(780, { at: 0.07, dur: 0.11, to: 1170, type: 'triangle', gain: 0.11 })
  },
  // Trava metálica e um acorde curto.
  powerArm: () => {
    noise({ dur: 0.03, filter: 'highpass', freq: 3000, gain: 0.3 })
    tone(1800, { dur: 0.05, type: 'square', gain: 0.04 })
    ;[523, 659, 784].forEach((f) => tone(f, { at: 0.06, dur: 0.35, type: 'triangle', gain: 0.08 }))
  },
  // "Ops": dois tons caindo.
  powerHit: () => {
    tone(660, { dur: 0.16, type: 'triangle', gain: 0.15 })
    tone(440, { at: 0.18, dur: 0.3, to: 380, type: 'triangle', gain: 0.15 })
  },
  shield: () => file('shield'),
  theme: () => file('theme'),
  investment: () => file('investment'),
  backpack: () => file('backpack'),
  resurrection: () => file('resurrection'),
  duelIntro: () => file('duelIntro'),
  duelFight: () => file('duelFight'),
  duelLastQuestion: () => file('duelLastQuestion'),
  duelBet: () => file('duelBet'),
  duelWin: () => file('duelWin'),
  duelLose: () => file('duelLose'),
  duelWatch: () => file('duelWatch'),

}

export function isMuted() {
  try {
    return localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false
  }
}

export function setMuted(muted: boolean) {
  try {
    localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
  } catch {
    // Sem armazenamento (aba anônima, por exemplo): vale só nesta visita.
  }
  mutedNow = muted
}

let mutedNow = isMuted()

/** Toca um som, se ele estiver ligado e o jogo não estiver no mudo. */
export function playSound(id: SoundId, arg?: number) {
  if (mutedNow || !SOUND_ENABLED[id]) return
  try {
    SYNTHS[id](arg)
  } catch {
    // Navegador sem Web Audio: o jogo segue em silêncio.
  }
}

/** Toca um som de propósito, mesmo desligado na lista (usado para ouvir na página de escolha). */
export function previewSound(id: SoundId, arg?: number) {
  SYNTHS[id](arg)
}

// Celulares só liberam o áudio depois de um toque na tela.
if (typeof window !== 'undefined') {
  window.addEventListener(
    'pointerdown',
    () => {
      if (mutedNow) return
      audio()
      for (const url of Object.keys(FILE_URLS)) void load(url.replace(/^.*\/|\.m4a$/g, ''))
    },
    { once: true },
  )
}
