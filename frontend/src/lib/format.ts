const moneyFormatters = new Map<string, Intl.NumberFormat>()

export function money(amount: number, currency = 'USD', decimals = 0): string {
  const key = `${currency}:${decimals}`
  let formatter = moneyFormatters.get(key)
  if (!formatter) {
    formatter = new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency,
      currencyDisplay: 'narrowSymbol',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    moneyFormatters.set(key, formatter)
  }
  return formatter.format(amount)
}

/** "2026-11-10" → Date local (sin corrimiento por zona horaria). */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toIsoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function addDays(iso: string, days: number): string {
  const date = parseDate(iso)
  date.setDate(date.getDate() + days)
  return toIsoDate(date)
}

const shortDate = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short' })
const longDate = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
const dateTime = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' })

export const formatShortDate = (iso: string) => shortDate.format(parseDate(iso)).replace('.', '')
export const formatDate = (iso: string) => longDate.format(parseDate(iso)).replace('.', '')

export function formatDateRange(fromIso: string, toIso: string): string {
  return `${formatShortDate(fromIso)} – ${formatDate(toIso)}`
}

export function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? timestamp : dateTime.format(date)
}

/** "06:50:00" → "06:50" */
export const formatTime = (time: string) => time.slice(0, 5)

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

export function formatStops(stops: number): string {
  if (stops === 0) return 'Directo'
  return stops === 1 ? '1 escala' : `${stops} escalas`
}

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export const shortId = (id: string) => id.slice(0, 8).toUpperCase()
