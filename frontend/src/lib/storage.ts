// Almacenamiento del navegador solo para comodidades de este visitante (el
// paquete que está armando, la clave del checkout). Nunca guarda la sesión:
// esa vive en una cookie HttpOnly que JavaScript no puede leer.
// Todo va en try/catch porque el almacenamiento puede estar bloqueado.

type Store = 'local' | 'session'

function backend(store: Store): Storage | null {
  try {
    return store === 'local' ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

export function readJson<T>(store: Store, key: string): T | null {
  try {
    const raw = backend(store)?.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function writeJson(store: Store, key: string, value: unknown): void {
  try {
    backend(store)?.setItem(key, JSON.stringify(value))
  } catch {
    // sin almacenamiento la app sigue funcionando; solo se pierde la comodidad
  }
}

export function remove(store: Store, key: string): void {
  try {
    backend(store)?.removeItem(key)
  } catch {
    // ídem
  }
}
