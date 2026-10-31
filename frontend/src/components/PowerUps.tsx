import { useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'
import { AVATAR_URLS } from '../lib/avatars'
import { playSound } from '../lib/sounds'
import { INSTANT, LEGENDARY_DECOY_HINT, LEGENDARY_HINT, LEGENDARY_STEAL_HINT, LEGENDARY_TOLL_HINT, POWERUP_INFO, type Kind, type PowerView } from '../lib/powerups'
import type { PlayerView, PowerUpUse } from '../types/events'

const ICON_STROKE = { stroke: '#12141B', strokeWidth: 1.8, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const }

export function PowerUpIcon({ kind, className }: { kind: Kind; className?: string }) {
  if (kind === 'double') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2.5" y="4" width="19" height="16" rx="4" fill="#FBBF24" {...ICON_STROKE} />
        <text x="12" y="16.3" textAnchor="middle" fontSize="10" fontWeight="900" fill="#12141B">×2</text>
      </svg>
    )
  }
  if (kind === 'peek') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M1.5 12S5.5 5 12 5s10.5 7 10.5 7-4 7-10.5 7S1.5 12 1.5 12Z" fill="#5EEAD4" {...ICON_STROKE} />
        <circle cx="12" cy="12" r="3.6" fill="#12141B" />
        <circle cx="13.2" cy="10.8" r="1.1" fill="#F8FAFC" />
      </svg>
    )
  }
  if (kind === 'extra_time') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="11" cy="13" r="8.5" fill="#BEF264" {...ICON_STROKE} />
        <path d="M11 8v5l3 2" fill="none" {...ICON_STROKE} />
        <path d="M9 2.5h4" {...ICON_STROKE} />
        <circle cx="19.5" cy="5.5" r="3.5" fill="#12141B" />
        <path d="M19.5 3.8v3.4M17.8 5.5h3.4" stroke="#BEF264" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'second_chance') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" fill="none" stroke="#12141B" strokeWidth="5" strokeLinecap="round" />
        <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" fill="none" stroke="#F9A8D4" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M18.5 2.5v5h-5" fill="none" {...ICON_STROKE} strokeWidth={2.2} />
        <text x="12" y="15.6" textAnchor="middle" fontSize="9" fontWeight="900" fill="#F8FAFC">2</text>
      </svg>
    )
  }
  if (kind === 'reverse') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="4" y="1.5" width="16" height="21" rx="2.5" fill="#EF4444" {...ICON_STROKE} />
        <ellipse cx="12" cy="12" rx="5.5" ry="8" transform="rotate(30 12 12)" fill="#F8FAFC" />
        <g fill="none" stroke="#EF4444" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8.2 14.2 12.4 8.4M9.6 8.2l2.9.1.1 2.9" />
          <path d="M15.8 9.8 11.6 15.6M14.4 15.8l-2.9-.1-.1-2.9" />
        </g>
      </svg>
    )
  }
  if (kind === 'scramble') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="1.5" y="3" width="10" height="10" rx="2" fill="#F0ABFC" {...ICON_STROKE} transform="rotate(-10 6.5 8)" />
        <rect x="12.5" y="10" width="10" height="10" rx="2" fill="#F0ABFC" {...ICON_STROKE} transform="rotate(12 17.5 15)" />
        <text x="6.5" y="11.3" textAnchor="middle" fontSize="8" fontWeight="900" fill="#12141B" transform="rotate(-10 6.5 8)">a</text>
        <text x="17.5" y="18.3" textAnchor="middle" fontSize="8" fontWeight="900" fill="#12141B" transform="rotate(12 17.5 15)">Z</text>
      </svg>
    )
  }
  if (kind === 'accelerator') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M13.5 1.5 4 13.5h6.5l-2 9 9.5-12h-6.5l2-9Z" fill="#FB923C" {...ICON_STROKE} />
      </svg>
    )
  }
  if (kind === 'mirror') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <ellipse cx="12" cy="10" rx="7" ry="8.5" fill="#67E8F9" {...ICON_STROKE} />
        <path d="M8.5 6.5 11 4M8 10l5-5" stroke="#F8FAFC" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M12 18.5v4M8.5 22.5h7" {...ICON_STROKE} />
      </svg>
    )
  }
  if (kind === 'magnifier') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="m14.5 14.5 7 7" stroke="#12141B" strokeWidth="5" strokeLinecap="round" />
        <path d="m14.5 14.5 7 7" stroke="#A16207" strokeWidth="2.8" strokeLinecap="round" />
        <circle cx="9.5" cy="9.5" r="7.5" fill="#FEF9C3" {...ICON_STROKE} strokeWidth={2.2} />
        <path d="M6 8a4 4 0 0 1 3-3" fill="none" stroke="#F8FAFC" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'silence') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="12" cy="12" r="9.5" fill="#CBD5E1" {...ICON_STROKE} />
        <path d="M12 7v5l3 2" fill="none" {...ICON_STROKE} />
        <path d="m4.5 4.5 15 15" stroke="#12141B" strokeWidth="4" strokeLinecap="round" />
        <path d="m4.5 4.5 15 15" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'fifty_fifty') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="#A78BFA" stroke="#12141B" strokeWidth="1.8" />
        <path d="M6 18 18 6" stroke="#12141B" strokeWidth="1.8" />
        <text x="8.2" y="11" textAnchor="middle" fontSize="7" fontWeight="900" fill="#12141B">50</text>
        <text x="15.8" y="18.6" textAnchor="middle" fontSize="7" fontWeight="900" fill="#12141B">50</text>
      </svg>
    )
  }
  if (kind === 'shield') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M12 2 4 5v6c0 5 3.4 9 8 11 4.6-2 8-6 8-11V5l-8-3Z" fill="#7DD3FC" stroke="#12141B" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M12 5.5v13M7.5 9.5h9" stroke="#F8FAFC" strokeWidth="1.6" strokeLinecap="round" opacity=".8" />
      </svg>
    )
  }
  if (kind === 'backpack') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M9 5V4a3 3 0 0 1 6 0v1" fill="none" {...ICON_STROKE} />
        <rect x="4" y="5" width="16" height="17" rx="4" fill="#D97706" {...ICON_STROKE} />
        <rect x="7.5" y="13" width="9" height="6" rx="1.5" fill="#FBBF24" {...ICON_STROKE} />
        <path d="M12 8.5v3M10.5 10h3" stroke="#F8FAFC" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'coup') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        {/* A coroa do dono do tema, derrubada e puxada para o lado. */}
        <path d="M4 16.5 3 7.5l4.5 3.5L11 5l3.5 6L19 7.5l-1 9Z" fill="#FBBF24" {...ICON_STROKE} transform="rotate(-16 11 12)" />
        <path d="M4.6 19.4h12.6" stroke="#12141B" strokeWidth="3.2" strokeLinecap="round" transform="rotate(-16 11 12)" />
        <path d="M4.6 19.4h12.6" stroke="#F59E0B" strokeWidth="1.6" strokeLinecap="round" transform="rotate(-16 11 12)" />
        <path d="M15.5 21.5h6m0 0-2.4-2.4m2.4 2.4-2.4 2.4" fill="none" stroke="#12141B" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M15.5 21.5h6m0 0-2.4-2.4m2.4 2.4-2.4 2.4" fill="none" stroke="#FB923C" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (kind === 'theme') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2" y="6" width="11" height="15" rx="2" fill="#C7D2FE" {...ICON_STROKE} transform="rotate(-12 7.5 13.5)" />
        <rect x="10" y="3" width="11" height="15" rx="2" fill="#818CF8" {...ICON_STROKE} transform="rotate(10 15.5 10.5)" />
        <path d="m15.6 7.2 1 2.1 2.3.3-1.7 1.6.4 2.3-2-1.1-2 1.1.4-2.3-1.7-1.6 2.3-.3 1-2.1Z" fill="#F8FAFC" transform="rotate(10 15.5 10.5)" />
      </svg>
    )
  }
  if (kind === 'investment') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2.5" y="2.5" width="19" height="19" rx="4" fill="#4ADE80" {...ICON_STROKE} />
        <path d="M6 16.5 10 12l3 2.5 5-6" fill="none" {...ICON_STROKE} strokeWidth={2.2} />
        <path d="M14.5 8.5H18V12" fill="none" {...ICON_STROKE} strokeWidth={2.2} />
      </svg>
    )
  }
  if (kind === 'toll') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M4 22V5.5a1.5 1.5 0 0 1 3 0V22" fill="#FDA4AF" {...ICON_STROKE} />
        <path d="M7 9h14v3.5H7Z" fill="#F8FAFC" {...ICON_STROKE} />
        <path d="M10 9 8.5 12.5M14 9l-1.5 3.5M18 9l-1.5 3.5" stroke="#F43F5E" strokeWidth="1.6" />
        <circle cx="16" cy="18" r="3.5" fill="#FBBF24" {...ICON_STROKE} />
        <path d="M16 16.5v3" stroke="#12141B" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'duel') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M3 3 6.5 4 16 13.5 13.5 16 4 6.5Z" fill="#FEF3C7" {...ICON_STROKE} />
        <path d="M21 3 17.5 4 8 13.5 10.5 16 20 6.5Z" fill="#FBBF24" {...ICON_STROKE} />
        <path d="m13 18 5-5M11 18l-5-5M16.5 16.5l3 3M7.5 16.5l-3 3" {...ICON_STROKE} strokeWidth={2.2} />
      </svg>
    )
  }
  if (kind === 'resurrection') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M12 21C7 17.5 3 14 3 9.5A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 9 2.5c0 4.5-4 8-9 11.5Z" fill="#FBBF24" {...ICON_STROKE} />
        <path d="M2 6.5 4.5 8M22 6.5 19.5 8M12 1.5V4" stroke="#FDE68A" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M12 9.5v6M9 12.5h6" stroke="#F8FAFC" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'decoy') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2" y="4" width="20" height="16" rx="3" fill="#C084FC" {...ICON_STROKE} />
        <path d="M5.5 10h9M5.5 14h6" stroke="#F8FAFC" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="18" cy="13" r="3.2" fill="#F8FAFC" {...ICON_STROKE} />
        <path d="M16.6 11.6 19.4 14.4M19.4 11.6l-2.8 2.8" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'flashbang') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="m12 1.5 2 5 5-2-2 5 5.5 2.5-5.5 2.5 2 5-5-2-2 5-2-5-5 2 2-5L1.5 12 7 9.5l-2-5 5 2 2-5Z" fill="#FEF08A" {...ICON_STROKE} />
        <circle cx="12" cy="12" r="3.5" fill="#F8FAFC" {...ICON_STROKE} />
      </svg>
    )
  }
  if (kind === 'cold_water') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M12 2.5C8 8 5.5 11.5 5.5 15a6.5 6.5 0 0 0 13 0c0-3.5-2.5-7-6.5-12.5Z" fill="#7DD3FC" {...ICON_STROKE} />
        <path d="M9 15.5a3 3 0 0 0 3 3" fill="none" stroke="#F8FAFC" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'free_pass') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2" y="6" width="20" height="12" rx="2.5" fill="#6EE7B7" {...ICON_STROKE} />
        <path d="M7 12h8.5M13 9l3 3-3 3" fill="none" stroke="#12141B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M19 8.5v7" stroke="#12141B" strokeWidth="1.4" strokeDasharray="1.6 1.6" />
      </svg>
    )
  }
  if (kind === 'mutiny') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M5 9 7 4l3 3 2-4 2 4 3-3 2 5Z" fill="#FDA4AF" {...ICON_STROKE} />
        <path d="M5 9h14v3H5Z" fill="#FB7185" {...ICON_STROKE} />
        <path d="M4 21 20 13" stroke="#12141B" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M4 21 20 13" stroke="#F43F5E" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'infiltrator') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M3 10c2-5 16-5 18 0l-2 1H5Z" fill="#CBD5E1" {...ICON_STROKE} />
        <path d="M5 11h14c0 6-3 10-7 10s-7-4-7-10Z" fill="#94A3B8" {...ICON_STROKE} />
        <path d="M6 14h12v3H6Z" fill="#12141B" />
        <circle cx="9" cy="15.5" r="1" fill="#F8FAFC" />
        <circle cx="15" cy="15.5" r="1" fill="#F8FAFC" />
      </svg>
    )
  }
  if (kind === 'gag') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="#FCD34D" {...ICON_STROKE} />
        <circle cx="9" cy="9.5" r="1.2" fill="#12141B" />
        <circle cx="15" cy="9.5" r="1.2" fill="#12141B" />
        <path d="M3.5 13.5h17v3.5h-17Z" fill="#A8A29E" {...ICON_STROKE} />
        <path d="M8 13.5v3.5M12 13.5v3.5M16 13.5v3.5" stroke="#12141B" strokeWidth="1.2" />
      </svg>
    )
  }
  if (kind === 'iron_captain') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M4 18 3 7l5 4 4-7 4 7 5-4-1 11Z" fill="#D4D4D8" {...ICON_STROKE} />
        <path d="M4 18h16v3H4Z" fill="#71717A" {...ICON_STROKE} />
        <circle cx="12" cy="13.5" r="1.6" fill="#12141B" />
      </svg>
    )
  }
  if (kind === 'tax') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M6 2.5h9l3.5 3.5v15.5H6Z" fill="#FEF3C7" {...ICON_STROKE} />
        <path d="M9 8h6M9 11h6" stroke="#B45309" strokeWidth="1.6" strokeLinecap="round" />
        <text x="12.2" y="19" textAnchor="middle" fontSize="7" fontWeight="900" fill="#B45309">%</text>
      </svg>
    )
  }
  if (kind === 'medkit') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2.5" y="6" width="19" height="14" rx="3" fill="#F8FAFC" {...ICON_STROKE} />
        <path d="M9 6V4h6v2" fill="none" {...ICON_STROKE} />
        <path d="M12 9.5v7M8.5 13h7" stroke="#EF4444" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'hide') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="8" cy="14" r="5.5" fill="#22C55E" {...ICON_STROKE} />
        <circle cx="16" cy="13" r="6" fill="#16A34A" {...ICON_STROKE} />
        <circle cx="12" cy="8.5" r="5" fill="#4ADE80" {...ICON_STROKE} />
        <circle cx="10.5" cy="13" r="1" fill="#12141B" />
        <circle cx="13.5" cy="13" r="1" fill="#12141B" />
      </svg>
    )
  }
  if (kind === 'curse') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M12 2.5c5 0 8.5 3.5 8.5 8 0 3-1.7 5-3.5 6v3.5h-10V16.5C5.2 15.5 3.5 13.5 3.5 10.5c0-4.5 3.5-8 8.5-8Z" fill="#A78BFA" {...ICON_STROKE} />
        <circle cx="8.7" cy="11" r="2" fill="#12141B" />
        <circle cx="15.3" cy="11" r="2" fill="#12141B" />
        <path d="M10 20v-2M14 20v-2" stroke="#12141B" strokeWidth="1.4" />
      </svg>
    )
  }
  if (kind === 'blood_pact') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M8 3c2.5 3.5 4 6 4 8a4 4 0 0 1-8 0c0-2 1.5-4.5 4-8Z" fill="#EF4444" {...ICON_STROKE} />
        <path d="M16 9c2.5 3.5 4 6 4 8a4 4 0 0 1-8 0c0-2 1.5-4.5 4-8Z" fill="#B91C1C" {...ICON_STROKE} />
        <path d="M9.5 14.5 14 16" stroke="#F8FAFC" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'dagger') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        {/* Lâmina afiada com sulco, a ponta suja de sangue e uma gota caindo. */}
        <path d="M11 7.1 16.8 14.2 20.5 20.5 14.2 16.8 7.1 11Z" fill="#E2E8F0" stroke="#12141B" strokeWidth="1.1" strokeLinejoin="round" />
        <path d="M9.4 9.4 15.8 15.8" stroke="#94A3B8" strokeWidth="0.9" strokeLinecap="round" />
        <path d="M16.8 14.2 20.5 20.5 14.2 16.8Q14.9 16.3 15.2 17Q15.4 18.1 15.9 17.8Q16.2 16.9 15.9 16.3Q16.7 16 16.3 15.4Q17 15.1 16.8 14.2Z" fill="#DC2626" />
        <path d="M17.6 16.6 18.8 18.6" stroke="#FCA5A5" strokeWidth="0.5" strokeLinecap="round" />
        <path d="M20.5 21.3Q21.8 22.9 20.5 23.7Q19.2 22.9 20.5 21.3Z" fill="#DC2626" stroke="#12141B" strokeWidth="0.6" />
        <path d="M5 12.6 12.6 5" stroke="#12141B" strokeWidth="3.4" strokeLinecap="round" />
        <path d="M5 12.6 12.6 5" stroke="#FBBF24" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M7.8 7.8 4.1 4.1" stroke="#12141B" strokeWidth="3.4" strokeLinecap="round" />
        <path d="M7.8 7.8 4.1 4.1" stroke="#B45309" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="3.1" cy="3.1" r="1.7" fill="#FBBF24" stroke="#12141B" strokeWidth="1.1" />
      </svg>
    )
  }
  if (kind === 'blessing') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <ellipse cx="12" cy="5" rx="6.5" ry="2.2" fill="none" stroke="#FDE047" strokeWidth="2" />
        <path d="M12 9.5 13.8 14l4.7.3-3.6 3 1.2 4.6L12 19.4l-4.1 2.5 1.2-4.6-3.6-3 4.7-.3Z" fill="#FDE68A" {...ICON_STROKE} />
      </svg>
    )
  }
  if (kind === 'short_fuse') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M4 20c3-1 5-3 6-6" fill="none" stroke="#12141B" strokeWidth="3.2" strokeLinecap="round" />
        <path d="M4 20c3-1 5-3 6-6" fill="none" stroke="#E5E7EB" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M13 3.5c2.8 2.3 5 5 5 8a5 5 0 0 1-10 0c0-2 1-3.6 2.3-4.8.2 1.6 1 2.4 1.9 2.6-.2-2.2.2-4 .8-5.8Z" fill="#F97316" {...ICON_STROKE} />
        <path d="M13 9.5c1.2 1.1 2.1 2.2 2.1 3.4a2.1 2.1 0 0 1-4.2 0c0-1.2.9-2.3 2.1-3.4Z" fill="#FDE047" />
      </svg>
    )
  }
  if (kind === 'double_bomb') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <circle cx="8.5" cy="14.5" r="5.5" fill="#334155" {...ICON_STROKE} />
        <circle cx="15.5" cy="14.5" r="5.5" fill="#475569" {...ICON_STROKE} />
        <path d="M15.5 9V6.5c0-1.5 1.5-2.5 3-2" fill="none" stroke="#12141B" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="19" cy="4" r="1.6" fill="#FB923C" />
        <text x="15.5" y="17.3" textAnchor="middle" fontSize="7" fontWeight="900" fill="#F8FAFC">2</text>
      </svg>
    )
  }
  if (kind === 'ghost_hint') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M3 21V11a6 6 0 0 1 12 0v10l-2-1.5L11 21l-2-1.5L7 21l-2-1.5Z" fill="#E0E7FF" {...ICON_STROKE} />
        <circle cx="7" cy="11" r="1.2" fill="#12141B" />
        <circle cx="11" cy="11" r="1.2" fill="#12141B" />
        <path d="M14 3.5h7a1.5 1.5 0 0 1 1.5 1.5v4A1.5 1.5 0 0 1 21 10.5h-3.5L15 13v-2.5h-1A1.5 1.5 0 0 1 12.5 9V5A1.5 1.5 0 0 1 14 3.5Z" fill="#A5B4FC" {...ICON_STROKE} />
        <text x="17.5" y="9.3" textAnchor="middle" fontSize="5.5" fontWeight="900" fill="#12141B">?</text>
      </svg>
    )
  }
  if (kind === 'thermometer') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <path d="M10 4a2 2 0 0 1 4 0v10.3a4 4 0 1 1-4 0Z" fill="#F8FAFC" {...ICON_STROKE} />
        <path d="M12 7.5v8" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" />
        <circle cx="12" cy="17.7" r="2.4" fill="#EF4444" />
        <path d="M15.5 6.5h2M15.5 9.5h2M15.5 12.5h2" stroke="#12141B" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    )
  }
  if (kind === 'double_potato') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <ellipse cx="9" cy="14" rx="6.2" ry="5" fill="#A3753B" transform="rotate(-18 9 14)" {...ICON_STROKE} />
        <ellipse cx="15.5" cy="11" rx="6.2" ry="5" fill="#FACC15" transform="rotate(-18 15.5 11)" {...ICON_STROKE} />
        <path d="M12.5 9.3c1-1.2 2.3-1.8 3.6-1.8" fill="none" stroke="#FEF9C3" strokeWidth="1.3" strokeLinecap="round" />
        <path d="M19 6.5l1.5-2.2" stroke="#12141B" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="20.8" cy="3.8" r="1.4" fill="#FB923C" />
      </svg>
    )
  }
  if (kind === 'scratch') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
        <rect x="2.5" y="5" width="19" height="14" rx="2.5" fill="#D4D4D8" stroke="#12141B" strokeWidth="1.8" />
        <path d="M6 15c2-3 3 1 5-2s3 1 5-2 2 0 2 0" fill="none" stroke="#FFC107" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="18" cy="8.5" r="1.3" fill="#12141B" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M8 5.5h8l-1.5 2.5c3.5 2 5.5 5 5.5 8.5 0 3-2.5 5-8 5s-8-2-8-5c0-3.5 2-6.5 5.5-8.5L8 5.5Z" fill="#34D399" stroke="#12141B" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M7.5 3.5h9" stroke="#12141B" strokeWidth="1.8" strokeLinecap="round" />
      <text x="12" y="18" textAnchor="middle" fontSize="8" fontWeight="900" fill="#12141B">$</text>
    </svg>
  )
}

const SCRATCH_RADIUS = 12
const SCRATCH_REVEAL = 0.9 // fração raspada que tira a cobertura

/** Cobertura prateada da raspadinha: some quando o jogador raspa a maior parte (e trava os toques até lá). */
export function ScratchCard({ active, className = '', children }: { active: boolean; className?: string; children: ReactNode }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const last = useRef<{ x: number; y: number } | null>(null)
  const moves = useRef(0)
  const [revealed, setRevealed] = useState(false)
  const covered = active && !revealed

  useLayoutEffect(() => {
    const canvas = canvasRef.current
    if (!covered || !canvas) return
    const dpr = window.devicePixelRatio || 1
    // Tamanho de layout: as alternativas entram com animação de escala, que o getBoundingClientRect mediria.
    const width = canvas.offsetWidth
    const height = canvas.offsetHeight
    canvas.width = Math.max(1, Math.round(width * dpr))
    canvas.height = Math.max(1, Math.round(height * dpr))
    const ctx = canvas.getContext('2d')!
    ctx.scale(dpr, dpr)
    const gradient = ctx.createLinearGradient(0, 0, width, height)
    gradient.addColorStop(0, '#A1A1AA')
    gradient.addColorStop(0.5, '#E4E4E7')
    gradient.addColorStop(1, '#A1A1AA')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, width, height)
    ctx.fillStyle = 'rgba(18, 20, 27, 0.35)'
    ctx.font = '18px "Lilita One", system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let y = 18; y < height; y += 36) {
      for (let x = (y / 36) % 2 ? 40 : 80; x < width + 40; x += 110) ctx.fillText('RASPE!', x, y)
    }
    // Só monta a cobertura uma vez por pergunta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const scratch = (e: PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !(e.buttons & 1 || e.pointerType === 'touch')) return
    const rect = canvas.getBoundingClientRect()
    const point = {
      x: ((e.clientX - rect.left) * canvas.offsetWidth) / Math.max(1, rect.width),
      y: ((e.clientY - rect.top) * canvas.offsetHeight) / Math.max(1, rect.height),
    }
    const ctx = canvas.getContext('2d')!
    ctx.globalCompositeOperation = 'destination-out'
    ctx.lineCap = 'round'
    ctx.lineWidth = SCRATCH_RADIUS * 2
    ctx.beginPath()
    ctx.moveTo(last.current?.x ?? point.x, last.current?.y ?? point.y)
    ctx.lineTo(point.x, point.y)
    ctx.stroke()
    last.current = point
    if (++moves.current % 6 === 0 && clearedFraction(canvas) >= SCRATCH_REVEAL) {
      playSound('select')
      setRevealed(true)
    }
  }

  return (
    <div className={`relative ${className}`}>
      {children}
      {covered && (
        <canvas
          ref={canvasRef}
          aria-label="Raspe para ver"
          className="absolute inset-0 z-10 size-full touch-none rounded-xl"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId)
            last.current = null
            scratch(e)
          }}
          onPointerMove={scratch}
          onPointerUp={() => (last.current = null)}
        />
      )}
    </div>
  )
}

const LENS = 96 // diâmetro da lupa, em px

/**
 * Lupa: tudo dentro fica borrado (impossível de ler), menos o círculo da lupa. A lupa é arrastada
 * pelo cabo; o vidro deixa os toques passarem, então dá para tocar na alternativa que se está lendo.
 */
export function Magnifier({ active, children }: { active: boolean; children: ReactNode }) {
  const boxRef = useRef<HTMLDivElement>(null)
  const grab = useRef<{ dx: number; dy: number } | null>(null)
  const [lens, setLens] = useState({ x: LENS / 2 + 8, y: LENS / 2 })

  const move = (e: PointerEvent<HTMLElement>) => {
    const box = boxRef.current
    if (!grab.current || !box) return
    const rect = box.getBoundingClientRect()
    const r = LENS / 2
    setLens({
      x: Math.min(rect.width - r / 2, Math.max(r / 2, e.clientX - rect.left - grab.current.dx)),
      y: Math.min(rect.height - r / 2, Math.max(r / 2, e.clientY - rect.top - grab.current.dy)),
    })
  }

  const hole = `radial-gradient(circle ${LENS / 2}px at ${lens.x}px ${lens.y}px, transparent 97%, black 100%)`
  return (
    <div ref={boxRef} className="relative flex flex-col gap-5">
      {children}
      {active && (
        <>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-20"
            style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)', maskImage: hole, WebkitMaskImage: hole }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute z-30 rounded-full border-[5px] border-[#12141B] shadow-[inset_0_0_0_3px_#FEF08A,0_6px_18px_rgba(0,0,0,0.5)]"
            style={{ width: LENS, height: LENS, left: lens.x - LENS / 2, top: lens.y - LENS / 2 }}
          />
          {/* Cabo: a única parte que se arrasta. */}
          <div
            role="slider"
            aria-label="Arraste a lupa"
            aria-valuenow={Math.round(lens.y)}
            className="absolute z-30 flex h-16 w-11 cursor-grab touch-none items-start justify-center active:cursor-grabbing"
            style={{ left: lens.x + LENS * 0.3, top: lens.y + LENS * 0.3, transform: 'rotate(-45deg)', transformOrigin: 'top center' }}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId)
              const rect = boxRef.current!.getBoundingClientRect()
              grab.current = { dx: e.clientX - rect.left - lens.x, dy: e.clientY - rect.top - lens.y }
            }}
            onPointerMove={move}
            onPointerUp={() => (grab.current = null)}
            onPointerCancel={() => (grab.current = null)}
          >
            <span className="h-14 w-4 rounded-full border-[3px] border-[#12141B] bg-[#A16207]" />
          </div>
        </>
      )}
    </div>
  )
}

/** Fração já raspada, olhando um pixel a cada 8 em cada direção. */
function clearedFraction(canvas: HTMLCanvasElement) {
  const { data, width, height } = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height)
  let clear = 0
  let total = 0
  for (let y = 0; y < height; y += 8) {
    for (let x = 0; x < width; x += 8) {
      total++
      if (data[(y * width + x) * 4 + 3] === 0) clear++
    }
  }
  return total ? clear / total : 1
}

/** O que está valendo nesta pergunta: quem jogou o quê em quem. As que tocam você aparecem primeiro. */
export function ActivePowerUps({
  game,
  players,
  playerId,
  concealed = false,
  survival = false,
  lines,
}: {
  game: PowerView
  players: PlayerView[]
  playerId: string | null
  concealed?: boolean
  survival?: boolean // Último de pé: fala de vidas, não de QI
  lines?: Partial<Record<Kind, string>> // trocam o aviso de quem usou o poder em si mesmo
}) {
  const name = (id: string | null) => (id === playerId ? 'você' : (players.find((p) => p.id === id)?.nickname ?? '?'))
  const cap = (text: string) => text[0].toUpperCase() + text.slice(1)
  // A lendária pega todo mundo: sempre é com você.
  const mine = (use: PowerUpUse) => use.legendary || use.by === playerId || use.target === playerId || use.reflected_by === playerId
  const uses = [...game.active].sort((a, b) => Number(mine(b)) - Number(mine(a)))
  // As que duram mais de uma pergunta: o anúncio de quem usou só aparece na primeira.
  const later = game.lasting.filter((l) => !game.active.some((u) => u.kind === l.kind && mine(u)))
  if (uses.length === 0 && later.length === 0) return null

  const line = (use: PowerUpUse) => {
    const by = name(use.by)
    const target = name(use.target)
    const info = POWERUP_INFO[use.kind]
    if (use.legendary) {
      if (use.kind === 'steal') return 'Roubo LENDÁRIO: você está de olho no QI de todo mundo!'
      return by === 'você' ? `Você jogou ${info.name} LENDÁRIO em todo mundo!` : `${cap(by)} jogou ${info.name} LENDÁRIO em todo mundo, inclusive em você!`
    }
    if (use.reflected_by && use.kind !== 'steal') {
      return `${cap(name(use.reflected_by))} devolveu ${info.name} com o Reverso: agora é ${by === 'você' ? 'em você' : `em ${by}`}!`
    }
    if (use.reflected_by) return `Você rebateu o Roubo de ${target} com o Reverso!`
    if (use.kind === 'theme') return by === 'você' ? `Você escolheu o tema: ${use.theme}!` : `${cap(by)} escolheu o tema: ${use.theme}!`
    if (use.kind === 'coup') return `Golpe! ${cap(by)} tomou ${use.theme} de ${target}: os +25% agora são ${by === 'você' ? 'seus' : `de ${by}`}!`
    if (!info.targeted) {
      const self: Partial<Record<Kind, string>> = {
        fifty_fifty: '50/50: duas erradas saíram.',
        shield: 'Seu Escudo está ativo por até 2 perguntas: o primeiro erro não tira QI.',
        double: 'Dobro: esta vale o dobro, para o bem e para o mal (na difícil, o erro tira o triplo).',
        peek: 'Espiar: veja nas alternativas o que a galera escolheu.',
        extra_time: 'Tempo extra: +5s e QI cheio o tempo todo nesta e nas próximas 2.',
        second_chance: 'Segunda chance nesta e na próxima: errou, tenta de novo.',
        reverse: 'Seu Reverso está pronto (só você sabe): o primeiro poder em você volta.',
        investment: 'Investimento valendo: cada acerto seguido rende mais. Não erre!',
        hide: 'Esconderijo: você pula esta pergunta sem perder vida.',
        ...(survival && {
          shield: 'Seu Escudo está ativo por até 2 perguntas: o primeiro erro não tira vida.',
          extra_time: 'Tempo extra: +5s nesta e nas próximas 2.',
        }),
        ...lines,
      }
      return by === 'você' ? self[use.kind]! : `${by} usou ${info.name}.`
    }
    if (use.kind === 'steal') return survival ? `Se ${target} perder uma vida, ela é sua!` : `Você está de olho no QI de ${target}!`
    if (use.target === playerId) {
      const hit: Partial<Record<Kind, string>> = {
        scratch: 'jogou Raspadinha em você! Raspe para ver.',
        scramble: 'jogou Embaralhar em você! Boa leitura.',
        accelerator: 'jogou Acelerador em você: um terço do tempo e sem QI cheio!',
        mirror: 'jogou Espelho em você!',
        magnifier: 'jogou Lupa em você! Arraste a lupa pelo cabo para ler.',
        toll: 'jogou Pedágio em você: cada resposta tem um preço!',
        curse: 'jogou Maldição em você: se errar, perde 2 vidas!',
        blood_pact: 'fez um Pacto de sangue com você: se perder vida, você perde também!',
        decoy: 'jogou Alternativa falsa em você: duas dessas são mentira!',
        flashbang: 'jogou Flashbang em você: leia rápido, ela estoura em 4 segundos!',
        silence: 'jogou Silêncio em você: por 2 perguntas, sem relógio, placar, revelação nem habilidades.',
        ...(survival && {
          accelerator: 'jogou Acelerador em você: um terço do tempo!',
          silence: 'jogou Silêncio em você: por 2 perguntas, sem relógio, vidas dos outros, revelação nem habilidades.',
        }),
      }
      return `${cap(by)} ${hit[use.kind]}`
    }
    return `${cap(by)} jogou ${info.name} em ${target}!`
  }

  return (
    <ul className={`flex flex-col gap-1.5 ${concealed ? 'invisible' : ''}`} aria-label="Habilidades valendo">
      {uses.map((use, index) => (
        <li
          key={`${use.by}-${use.kind}-${use.target}-${use.legendary}`}
          className={`avatar-pop flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold ${
            use.legendary ? 'legendary' : `${POWERUP_INFO[use.kind].tone} ${mine(use) ? 'ring-1 ring-brand/60' : 'opacity-70'}`
          }`}
          style={{ animationDelay: `${index * 0.1}s` }}
        >
          <PowerUpIcon kind={use.kind} className="size-5 shrink-0" />
          <span className="min-w-0">{line(use)}</span>
        </li>
      ))}
      {later.map((l) => (
        <li key={l.kind} className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold ring-1 ring-brand/60 ${POWERUP_INFO[l.kind].tone}`}>
          <PowerUpIcon kind={l.kind} className="size-5 shrink-0" />
          <span className="min-w-0">
            {POWERUP_INFO[l.kind].name} ainda valendo ({l.total - l.rounds_left + 1} de {l.total}){l.rounds_left === 1 && l.kind !== 'extra_time' ? ': esta é a última pergunta.' : '.'}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Ícones das habilidades que se usam durante a pergunta (50/50 e Espiar): tocou, vale na hora. */
export function InstantPowerUps({ game, playerId, onUse }: { game: PowerView; playerId: string | null; onUse: (kind: Kind) => Promise<string | null> }) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const kinds = [...new Set(game.powerups.filter((kind) => INSTANT.includes(kind)))]
  if (!game.powers_round || kinds.length === 0) return null
  const inUse = (kind: Kind) => game.active.some((u) => u.kind === kind && u.by === playerId)
  const count = (kind: Kind) => game.powerups.filter((k) => k === kind).length

  return (
    <div className="flex items-center justify-end gap-2">
      {error && <span className="mr-auto text-sm text-red-300">{error}</span>}
      {kinds.map((kind) => (
        <button
          key={kind}
          disabled={busy || inUse(kind)}
          onClick={async () => {
            playSound('powerArm')
            setBusy(true)
            setError(await onUse(kind))
            setBusy(false)
          }}
          className={`btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-semibold ${inUse(kind) ? 'opacity-50' : ''}`}
          aria-label={`Usar ${POWERUP_INFO[kind].name}`}
        >
          <PowerUpIcon kind={kind} className="size-6" />
          {POWERUP_INFO[kind].name}
          {count(kind) > 1 && <span className="text-xs opacity-70">×{count(kind)}</span>}
        </button>
      ))}
    </div>
  )
}

interface BarProps {
  powers: boolean // no clássico a barra é só o botão de pular
  game: PowerView
  players: PlayerView[]
  playerId: string | null
  targetIds?: string[] // quem pode ser alvo; sem isso, todos os outros
  hints?: Partial<Record<Kind, string>> // explicações que trocam as do POWERUP_INFO
  lockedNote?: string // por que não dá para armar agora
  emptyNote?: string // sem nenhuma habilidade na mão
  onArm: (kind: Kind, target: string | null, legendary?: boolean, theme?: string | null) => Promise<string | null>
  onSkip: () => Promise<string | null>
}

export function PowerUpBar({ powers, game, players, playerId, targetIds, hints, lockedNote, emptyNote, onArm, onSkip }: BarProps) {
  const [selected, setSelected] = useState<{ kind: Kind; legendary: boolean; mythic?: boolean } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [skipped, setSkipped] = useState(false)
  const connected = players.filter((p) => p.connected)
  const readyCount = connected.filter((p) => game.ready.includes(p.id)).length
  const isReady = skipped || (playerId !== null && game.ready.includes(playerId))
  const targets = players.filter((p) => p.id !== playerId && (!targetIds || targetIds.includes(p.id)))
  const hint = (kind: Kind) => hints?.[kind] ?? POWERUP_INFO[kind].hint

  const arm = async (kind: Kind, target: string | null, legendary = false, theme: string | null = null) => {
    playSound(kind === 'backpack' ? 'backpack' : kind === 'theme' ? 'theme' : 'powerArm')
    setSelected(null)
    setError(await onArm(kind, target, legendary, theme))
  }

  const skip = async () => {
    playSound('skip')
    setSkipped(true)
    const failure = await onSkip()
    if (failure) setSkipped(false)
  }

  let body
  if (!powers) {
    body = <p className="text-sm text-steel">Todo mundo leu? Pulem juntos para a próxima.</p>
  } else if (game.armed) {
    const info = POWERUP_INFO[game.armed.kind]
    const target = players.find((p) => p.id === game.armed?.target)
    body = game.armed.legendary ? (
      <p className="legendary flex items-center gap-2 rounded-xl px-3 py-1.5 font-semibold">
        <PowerUpIcon kind={game.armed.kind} className="size-6 shrink-0" />
        Na próxima: {info.name} LENDÁRIO em todo mundo!
      </p>
    ) : (
      <p className="flex items-center gap-2 font-semibold">
        <PowerUpIcon kind={game.armed.kind} className="size-6 shrink-0" />
        {game.armed.theme ? `Tema da próxima: ${game.armed.theme}!` : `Na próxima: ${info.name}${target ? ` em ${target.nickname}` : ''}!`}
      </p>
    )
  } else if (selected?.mythic) {
    const info = POWERUP_INFO[selected.kind]
    body = (
      <div className="flex flex-col gap-2">
        <p className="flex items-center gap-2 text-sm">
          <PowerUpIcon kind={selected.kind} className="size-6 shrink-0" />
          <span>
            <span className="font-bold text-amber-200">{info.name} MÍTICO:</span> {hint(selected.kind)}
          </span>
        </p>
        {(selected.kind === 'duel' || selected.kind === 'dagger') && (
          <>
            <p className="text-sm font-semibold text-steel">{selected.kind === 'duel' ? 'Quem vai para o X1?' : 'Em quem cravar a Adaga?'}</p>
            <div className="flex flex-wrap gap-2">
              {targets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => void arm(selected.kind, p.id)}
                  className="btn-3d btn-sm mythic flex items-center gap-1.5 rounded-xl py-1 pr-3 pl-1 text-sm font-semibold"
                >
                  <img src={AVATAR_URLS[p.avatar]} alt="" className="size-7" />
                  <span className="max-w-24 truncate">{p.nickname}</span>
                </button>
              ))}
            </div>
          </>
        )}
        <div className="flex gap-2">
          {selected.kind !== 'duel' && selected.kind !== 'dagger' && (
            <button onClick={() => void arm(selected.kind, null)} className="btn-3d btn-sm mythic flex-1 rounded-xl py-2 font-display text-lg">
              Usar agora
            </button>
          )}
          <button onClick={() => setSelected(null)} className="btn-3d btn-sm btn-dark rounded-xl px-4 py-2 font-semibold text-steel">
            Cancelar
          </button>
        </div>
      </div>
    )
  } else if (selected?.legendary) {
    const info = POWERUP_INFO[selected.kind]
    body = (
      <div className="flex flex-col gap-2">
        <p className="flex items-center gap-2 text-sm">
          <PowerUpIcon kind={selected.kind} className="size-6 shrink-0" />
          <span>
            <span className="font-bold text-brand">{info.name} LENDÁRIO:</span>{' '}
            {selected.kind === 'steal' ? LEGENDARY_STEAL_HINT : selected.kind === 'toll' ? LEGENDARY_TOLL_HINT : selected.kind === 'decoy' ? LEGENDARY_DECOY_HINT : `${info.hint} ${LEGENDARY_HINT}`}
          </span>
        </p>
        <div className="flex gap-2">
          <button onClick={() => void arm(selected.kind, null, true)} className="btn-3d btn-sm btn-brand flex-1 rounded-xl py-2 font-display text-lg text-ink">
            Jogar em todo mundo
          </button>
          <button onClick={() => setSelected(null)} className="btn-3d btn-sm btn-dark rounded-xl px-4 py-2 font-semibold text-steel">
            Cancelar
          </button>
        </div>
      </div>
    )
  } else if (selected) {
    const info = POWERUP_INFO[selected.kind]
    body = (
      <div className="flex flex-col gap-2">
        <p className="flex items-center gap-2 text-sm">
          <PowerUpIcon kind={selected.kind} className="size-6 shrink-0" />
          <span>
            <span className="font-bold">{info.name}:</span> {hint(selected.kind)}
          </span>
        </p>
        {selected.kind === 'theme' ? (
          <>
            <p className="text-sm font-semibold text-steel">Qual tema?</p>
            <div className="flex flex-wrap gap-2">
              {game.theme_choices.map((theme) => (
                <button
                  key={theme}
                  onClick={() => void arm(selected.kind, null, false, theme)}
                  className="btn-3d btn-sm btn-dark rounded-xl px-3 py-1.5 text-sm font-semibold"
                >
                  {theme}
                </button>
              ))}
            </div>
          </>
        ) : info.targeted ? (
          <>
            <p className="text-sm font-semibold text-steel">Em quem?</p>
            <div className="flex flex-wrap gap-2">
              {targets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => void arm(selected.kind, p.id)}
                  className="btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl py-1 pr-3 pl-1 text-sm font-semibold"
                >
                  <img src={AVATAR_URLS[p.avatar]} alt="" className="size-7" />
                  <span className="max-w-24 truncate">{p.nickname}</span>
                </button>
              ))}
            </div>
          </>
        ) : null}
        <div className="flex gap-2">
          {!info.targeted && selected.kind !== 'theme' && (
            <button onClick={() => void arm(selected.kind, null)} className="btn-3d btn-sm btn-brand flex-1 rounded-xl py-2 font-display text-lg text-ink">
              {selected.kind === 'backpack' ? 'Abrir agora' : selected.kind === 'medkit' ? 'Usar agora' : 'Usar na próxima'}
            </button>
          )}
          <button onClick={() => setSelected(null)} className="btn-3d btn-sm btn-dark rounded-xl px-4 py-2 font-semibold text-steel">
            Cancelar
          </button>
        </div>
      </div>
    )
  } else if (game.powerups.length === 0 && game.legendary_powerups.length === 0 && game.mythic_powerups.length === 0) {
    body = <p className="text-sm text-steel">{emptyNote ?? 'Sem habilidades. Acerte 3 seguidas para ganhar uma.'}</p>
  } else {
    body = (
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap gap-2">
          {game.powerups.map((kind, index) =>
            INSTANT.includes(kind) ? (
              // 50/50 e Espiar se usam pelo ícone na tela da pergunta, não aqui.
              <span
                key={`${kind}-${index}`}
                title={hint(kind)}
                className="flex items-center gap-1.5 rounded-xl bg-[#232b3f]/60 px-3 py-1.5 font-semibold text-steel"
              >
                <PowerUpIcon kind={kind} className="size-6" />
                <span className="flex flex-col leading-tight">
                  {POWERUP_INFO[kind].name}
                  <span className="text-[0.65rem] font-normal">usar na pergunta</span>
                </span>
              </span>
            ) : (
              <button
                key={`${kind}-${index}`}
                onClick={() => {
                  playSound('select')
                  setSelected({ kind, legendary: false })
                }}
                disabled={!game.can_arm && kind !== 'backpack'}
                className={`btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${game.can_arm || kind === 'backpack' ? '' : 'opacity-50'}`}
              >
                <PowerUpIcon kind={kind} className="size-6" />
                {POWERUP_INFO[kind].name}
              </button>
            ),
          )}
          {game.mythic_powerups.map((kind, index) => (
            <button
              key={`mythic-${kind}-${index}`}
              onClick={() => {
                playSound('select')
                setSelected({ kind, legendary: false, mythic: true })
              }}
              className="btn-3d btn-sm mythic mythic-pulse flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold"
            >
              <PowerUpIcon kind={kind} className="size-6" />
              <span className="flex flex-col text-left leading-tight">
                {POWERUP_INFO[kind].name}
                <span className="text-[0.65rem] font-bold tracking-wide uppercase">Mítico</span>
              </span>
            </button>
          ))}
          {game.legendary_powerups.map((kind, index) => (
            <button
              key={`legendary-${kind}-${index}`}
              onClick={() => {
                playSound('select')
                setSelected({ kind, legendary: true })
              }}
              disabled={!game.can_arm}
              className={`btn-3d btn-sm legendary legendary-pulse flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${game.can_arm ? '' : 'opacity-50'}`}
            >
              <PowerUpIcon kind={kind} className="size-6" />
              <span className="flex flex-col text-left leading-tight">
                {POWERUP_INFO[kind].name}
                <span className="text-[0.65rem] font-bold tracking-wide uppercase">Lendário</span>
              </span>
            </button>
          ))}
        </div>
        <p className="text-xs text-steel">{game.can_arm ? 'Toque para usar na próxima pergunta.' : (lockedNote ?? 'Habilidades não valem na aposta nem na final.')}</p>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 rounded-xl bg-panel px-3 py-2.5">
      <div className="min-w-0 flex-1">
        {body}
        {error && <p className="mt-1 text-sm text-red-300">{error}</p>}
      </div>
      <button
        onClick={() => void skip()}
        disabled={isReady}
        className={`btn-3d btn-sm shrink-0 rounded-xl px-3 py-1.5 text-sm font-semibold ${isReady ? 'btn-dark is-pressed text-steel' : 'btn-dark text-chalk'}`}
      >
        {isReady ? 'Pronto' : 'Pular'}
        <span className="block text-xs text-steel">
          {readyCount}/{connected.length}
        </span>
      </button>
    </div>
  )
}
