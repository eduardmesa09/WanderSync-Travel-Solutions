import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { gql } from '../api/graphql'
import { LOGIN, LOGOUT, ME, REGISTER, type User } from '../api/operations'

interface AuthContextValue {
  user: User | null
  /** true mientras se consulta `me` al cargar la página. */
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (email: string, password: string, fullName: string) => Promise<User>
  logout: () => Promise<void>
  /** Para cuando el gateway responde UNAUTHENTICATED (la sesión expiró). */
  forget: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // La cookie es HttpOnly: la única forma de saber si hay sesión es preguntar.
  useEffect(() => {
    gql<{ me: User | null }>(ME)
      .then((data) => setUser(data.me))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const data = await gql<{ login: User }>(LOGIN, { email, password })
    setUser(data.login)
    return data.login
  }, [])

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const data = await gql<{ register: User }>(REGISTER, { email, password, fullName })
    setUser(data.register)
    return data.register
  }, [])

  const logout = useCallback(async () => {
    try {
      await gql<{ logout: boolean }>(LOGOUT)
    } finally {
      setUser(null)
    }
  }, [])

  const forget = useCallback(() => setUser(null), [])

  const value = useMemo(
    () => ({ user, loading, login, register, logout, forget }),
    [user, loading, login, register, logout, forget],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return context
}
