import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { money } from '../lib/format'
import { useCountUp, useReveal } from '../lib/motion'
import { useAuth } from '../state/auth'
import { Icon } from './Icon'

/** Precio con contador ascendente (count-up que desacelera y se sostiene). */
export function AnimatedPrice({ amount, currency = 'USD', decimals = 0 }: { amount: number; currency?: string; decimals?: number }) {
  const value = useCountUp(amount)
  return <span className="tabular">{money(value, currency, decimals)}</span>
}

export function Spinner({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="spinner" role="status">
      <span className="spinner__ring" />
      <span>{label}</span>
    </div>
  )
}

export function Alert({ tone = 'danger', children }: { tone?: 'danger' | 'warning' | 'info' | 'success'; children: ReactNode }) {
  return (
    <div className={`alert alert--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon name={tone === 'success' ? 'check' : tone === 'info' ? 'sparkle' : 'alert'} size={18} />
      <div>{children}</div>
    </div>
  )
}

/** Encabezado de sección con el subrayado dorado que se barre al aparecer. */
export function SectionTitle({ title, subtitle, align = 'center' }: { title: string; subtitle?: string; align?: 'center' | 'left' }) {
  const ref = useReveal<HTMLDivElement>()
  return (
    <div ref={ref} className={`section-title section-title--${align} reveal`}>
      <h2>{title}</h2>
      <span className="section-title__rule" />
      {subtitle && <p>{subtitle}</p>}
    </div>
  )
}

/** Banda superior de las páginas internas, con foto de fondo. */
export function PageBand({ title, subtitle, image = '/images/hero-tayrona.jpg', children }: {
  title: string
  subtitle?: string
  image?: string
  children?: ReactNode
}) {
  return (
    <section className="page-band" style={{ backgroundImage: `url(${image})` }}>
      <div className="page-band__shade" />
      <div className="container page-band__inner">
        <h1 className="page-band__title">{title}</h1>
        {subtitle && <p className="page-band__subtitle">{subtitle}</p>}
        {children}
      </div>
    </section>
  )
}

/** Exige sesión: sin ella manda a /ingresar y luego regresa aquí. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Verificando tu sesión…" />
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/ingresar?next=${next}`} replace />
  }
  return <>{children}</>
}
