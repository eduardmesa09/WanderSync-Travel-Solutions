import { Link } from 'react-router-dom'
import { PHOTO_CREDITS } from '../lib/destinations'
import { Logo } from './Icon'

export function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__grid">
        <div>
          <Logo light />
          <p className="footer__about">
            Paquetes turísticos dinámicos: combina vuelo, hotel y auto en una sola reserva. Si un paso falla, todo
            se revierte automáticamente.
          </p>
        </div>
        <div>
          <h4>Explora</h4>
          <ul>
            <li><Link to="/buscar">Buscar paquete</Link></li>
            <li><a href="/#destinos">Destinos</a></li>
            <li><Link to="/reservas">Mis reservas</Link></li>
          </ul>
        </div>
        <div>
          <h4>Tu reserva</h4>
          <ul>
            <li>Precios en USD, tomados de Kayak</li>
            <li>Cobro simulado (proyecto académico)</li>
            <li>Sesión protegida con cookie HttpOnly</li>
          </ul>
        </div>
      </div>
      <div className="container footer__bottom">
        <span>© {new Date().getFullYear()} WanderSync Travel Solutions · Parcial de Patrones Arquitectónicos Avanzados</span>
        <span className="footer__credits">
          Fotos de Wikimedia Commons:{' '}
          {PHOTO_CREDITS.map((c, i) => (
            <span key={c.url}>
              <a href={c.url} target="_blank" rel="noreferrer">
                {c.place}
              </a>{' '}
              ({c.author}, {c.license}){i < PHOTO_CREDITS.length - 1 ? ' · ' : ''}
            </span>
          ))}
        </span>
      </div>
    </footer>
  )
}

/** Separador ondulado entre secciones, como el de la referencia visual. */
export function Wave({ flip = false, color = 'var(--sand)' }: { flip?: boolean; color?: string }) {
  return (
    <svg
      className={`wave ${flip ? 'wave--flip' : ''}`}
      viewBox="0 0 1440 70"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M0 38 C 160 8, 320 8, 480 34 S 800 66, 960 40 S 1280 6, 1440 30 L1440 70 L0 70 Z"
        fill={color}
      />
    </svg>
  )
}
