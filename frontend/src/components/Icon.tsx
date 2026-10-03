// Íconos de trazo, en línea para no depender de librerías externas.

const PATHS = {
  plane: 'M2.5 19h19M3.8 14.6l3 2.6c.4.3 1 .4 1.5.2l11.3-4.9a2 2 0 0 0-1.6-3.7l-4.1 1.8-6-4.5-2 .9 3.6 5-3.7 1.6-2.7-1.5-1.6.7z',
  bed: 'M3 18v-11M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5M7 11.5a1.5 1.5 0 1 0 0-.01',
  car: 'M5 17h14M3 17v-4l2-5a2 2 0 0 1 1.9-1.3h10.2A2 2 0 0 1 19 8l2 5v4h-2M5 17H3M7 17a2 2 0 1 0 0 .01M17 17a2 2 0 1 0 0 .01M3.5 12h17',
  card: 'M3 6h18v12H3zM3 10h18M7 15h4',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  undo: 'M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
  menu: 'M4 7h16M4 12h16M4 17h16',
  star: 'M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.4M18 14.5a7 7 0 0 1 4 6.5',
  bag: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  calendar: 'M4 6h16v15H4zM4 10h16M8 3v5M16 3v5',
  pin: 'M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12zM12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10',
  coffee: 'M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 3v3M12 3v3',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.4-2.3 1a7.4 7.4 0 0 0-1.7-1L15 3.5h-4l-.4 2.6a7.4 7.4 0 0 0-1.7 1l-2.3-1-2 3.4 2 1.5a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.4 2.3-1a7.4 7.4 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7.4 7.4 0 0 0 1.7-1l2.3 1 2-3.4z',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  alert: 'M12 3l10 18H2zM12 10v5M12 18v.01',
  snow: 'M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9',
  route: 'M6 19a2 2 0 1 0 0-.01M18 5a2 2 0 1 0 0-.01M6 17V9a4 4 0 0 1 4-4h2M18 7v8a4 4 0 0 1-4 4h-2',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className={`logo ${light ? 'logo--light' : ''}`}>
      <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden="true">
        <path d="M33 8 L33 46 L13 46 Z" fill="var(--gold)" />
        <path d="M37 15 L37 46 L52 46 Z" fill="currentColor" opacity="0.85" />
        <path d="M9 51 Q32 60 55 51" stroke="var(--gold)" strokeWidth="3.5" fill="none" strokeLinecap="round" />
      </svg>
      <span className="logo__text">
        WanderSync
        <small>Travel</small>
      </span>
    </span>
  )
}
