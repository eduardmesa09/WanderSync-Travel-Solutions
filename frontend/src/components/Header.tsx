import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../state/auth'
import { hasItems, usePackage } from '../state/package'
import { Icon, Logo } from './Icon'

export function Header({ overlay = false }: { overlay?: boolean }) {
  const { user, loading, logout } = useAuth()
  const { selection } = usePackage()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => setOpen(false), [location.pathname])

  useEffect(() => {
    if (!overlay) return
    const onScroll = () => setScrolled(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [overlay])

  const itemCount = selection ? [selection.flight, selection.hotel, selection.car].filter(Boolean).length : 0

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <>
      <div className="topbar">
        <div className="container topbar__inner">
          <span>
            <Icon name="shield" size={14} /> Vuelo + hotel + auto en una sola reserva
          </span>
          <span className="topbar__right">Bogotá · Medellín · Cartagena · Santa Marta</span>
        </div>
      </div>
      <header className={`header ${overlay ? 'header--overlay' : ''} ${scrolled ? 'header--scrolled' : ''}`}>
        <div className="container header__inner">
          <Link to="/" aria-label="WanderSync, inicio">
            <Logo light />
          </Link>

          <button
            className="header__toggle"
            aria-label="Abrir menú"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <Icon name={open ? 'x' : 'menu'} size={24} />
          </button>

          <nav className={`nav ${open ? 'nav--open' : ''}`} aria-label="Principal">
            <NavLink to="/" end>
              Inicio
            </NavLink>
            <a href="/#destinos">Destinos</a>
            <NavLink to="/buscar">Buscar paquete</NavLink>
            <a href="/#como-funciona">Cómo funciona</a>
            {user && <NavLink to="/reservas">Mis reservas</NavLink>}
            {hasItems(selection) && (
              <NavLink to="/checkout" className="nav__cart">
                Mi paquete <span className="nav__count">{itemCount}</span>
              </NavLink>
            )}
            {!loading &&
              (user ? (
                <span className="nav__user">
                  <span className="nav__hello">
                    <Icon name="user" size={15} /> {user.fullName.split(' ')[0]}
                  </span>
                  <button className="btn btn--pill btn--small btn--ghost-light" onClick={handleLogout}>
                    Salir
                  </button>
                </span>
              ) : (
                <Link to="/ingresar" className="btn btn--pill btn--small btn--gold">
                  Iniciar sesión
                </Link>
              ))}
          </nav>
        </div>
      </header>
    </>
  )
}
