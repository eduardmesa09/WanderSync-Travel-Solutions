// Cliente GraphQL mínimo. Toda la comunicación con el backend pasa por aquí,
// siempre por POST al gateway y siempre con la cookie de sesión.

const ENDPOINT = import.meta.env.VITE_GRAPHQL_URL || '/graphql'

export type ErrorCode =
  | 'UNAUTHENTICATED'
  | 'BAD_USER_INPUT'
  | 'RATE_LIMITED'
  | 'NOT_FOUND'
  | 'SERVICE_UNAVAILABLE'
  | 'SERVICE_ERROR'
  | 'NETWORK_ERROR'
  | 'UNKNOWN'

export interface GraphQLErrorEntry {
  message: string
  path?: (string | number)[]
  extensions?: { code?: ErrorCode; retryAfter?: number }
}

export class ApiError extends Error {
  readonly code: ErrorCode
  readonly retryAfter?: number

  constructor(message: string, code: ErrorCode, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.retryAfter = retryAfter
  }
}

export interface GraphQLResult<T> {
  data: T | null
  errors: GraphQLErrorEntry[]
}

function toApiError(entry: GraphQLErrorEntry): ApiError {
  return new ApiError(entry.message, entry.extensions?.code ?? 'UNKNOWN', entry.extensions?.retryAfter)
}

/**
 * Ejecuta una operación y devuelve datos y errores por separado. Sirve cuando
 * se aceptan respuestas parciales: si el servicio de autos está caído, la
 * búsqueda trae vuelos y hoteles y un error en la ruta `cars`.
 */
export async function request<T>(query: string, variables?: Record<string, unknown>): Promise<GraphQLResult<T>> {
  let response: Response
  try {
    response = await fetch(ENDPOINT, {
      method: 'POST', // el gateway desactiva GET para evitar CSRF
      credentials: 'include', // la sesión viaja en una cookie HttpOnly
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query, variables }),
    })
  } catch {
    throw new ApiError('No pudimos conectar con el servidor. Revisa que el backend esté arriba.', 'NETWORK_ERROR')
  }

  let body: { data?: T | null; errors?: GraphQLErrorEntry[] }
  try {
    body = await response.json()
  } catch {
    throw new ApiError(`El servidor respondió algo inesperado (HTTP ${response.status}).`, 'SERVICE_ERROR')
  }

  const errors = body.errors ?? []
  // Límite general del gateway: responde 429 sin datos.
  if (response.status === 429 || (!body.data && errors.length > 0)) {
    throw toApiError(errors[0] ?? { message: 'Demasiadas solicitudes', extensions: { code: 'RATE_LIMITED' } })
  }
  return { data: body.data ?? null, errors }
}

/** Ejecuta una operación y falla ante cualquier error. */
export async function gql<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
  const { data, errors } = await request<T>(query, variables)
  if (errors.length > 0) throw toApiError(errors[0])
  if (!data) throw new ApiError('Respuesta vacía del servidor', 'SERVICE_ERROR')
  return data
}

/** Mensaje listo para mostrar al usuario. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'RATE_LIMITED') {
      return error.retryAfter
        ? `Demasiados intentos. Espera ${error.retryAfter} s e inténtalo de nuevo.`
        : 'Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.'
    }
    return error.message
  }
  return 'Ocurrió un error inesperado.'
}
