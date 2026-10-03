import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { describeError } from '../api/graphql'
import { Icon, Logo } from '../components/Icon'
import { Alert } from '../components/common'
import { useAuth } from '../state/auth'

const MIN_PASSWORD = 10 // mismo mínimo que valida el gateway

/** Solo rutas internas: evita redirecciones abiertas con ?next=https://… */
function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

export function Login() {
  return <AuthPage mode="login" />
}

export function Register() {
  return <AuthPage mode="register" />
}

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isLogin = mode === 'login'

  if (user && !busy) return <Navigate to={next} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setError(null)
    if (!isLogin && password.length < MIN_PASSWORD) {
      setError(`La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`)
      return
    }
    setBusy(true)
    try {
      if (isLogin) await login(email, password)
      else await register(email, password, fullName)
      navigate(next, { replace: true })
    } catch (e) {
      setError(describeError(e))
      setBusy(false)
    }
  }

  const otherLink = `${isLogin ? '/registro' : '/ingresar'}${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`

  return (
    <div className="auth">
      <div className="auth__media" style={{ backgroundImage: `url(${isLogin ? '/images/cartagena.jpg' : '/images/santa-marta.jpg'})` }}>
        <div className="auth__shade" />
        <div className="auth__quote">
          <Logo light />
          <p>“Vuelo, hotel y auto en una sola reserva. Todo o nada.”</p>
        </div>
      </div>
      <div className="auth__panel">
        <form className="auth__form" onSubmit={submit} noValidate={false}>
          <h1>{isLogin ? 'Bienvenido de nuevo' : 'Crea tu cuenta'}</h1>
          <p className="muted">{isLogin ? 'Inicia sesión para reservar tu paquete.' : 'Regístrate en menos de un minuto.'}</p>

          {error && <Alert>{error}</Alert>}

          {!isLogin && (
            <label className="field field--stacked">
              <span className="field__label"><Icon name="user" size={14} /> Nombre completo</span>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required maxLength={100} autoComplete="name" />
            </label>
          )}
          <label className="field field--stacked">
            <span className="field__label">Correo electrónico</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} autoComplete="email" />
          </label>
          <label className="field field--stacked">
            <span className="field__label">Contraseña</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={isLogin ? undefined : MIN_PASSWORD}
              maxLength={128}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
            />
            {!isLogin && <span className="field__hint">Mínimo {MIN_PASSWORD} caracteres.</span>}
          </label>

          <button className="btn btn--pill btn--gold btn--block" disabled={busy}>
            {busy ? 'Un momento…' : isLogin ? 'Iniciar sesión' : 'Crear cuenta'}
          </button>
          <p className="auth__switch">
            {isLogin ? '¿No tienes cuenta?' : '¿Ya tienes cuenta?'}{' '}
            <Link to={otherLink}>{isLogin ? 'Regístrate' : 'Inicia sesión'}</Link>
          </p>
          <p className="auth__secure">
            <Icon name="shield" size={14} /> Contraseñas con Argon2id · sesión renovada al ingresar · límite de intentos
          </p>
        </form>
      </div>
    </div>
  )
}
