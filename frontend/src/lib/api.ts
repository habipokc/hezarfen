/** Human-readable message from an ICD §7.1 error body (`{"error": {"code", "message"}}`). */
export function apiErrorMessage(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'error' in body) {
    const error = (body as { error: unknown }).error
    if (typeof error === 'object' && error !== null && 'message' in error) {
      const message = (error as { message: unknown }).message
      if (typeof message === 'string' && message) return message
    }
  }
  return `HTTP ${status}`
}

/** fetch + JSON with ICD errors turned into thrown `Error`s carrying the server's message. */
export async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init)
  if (resp.status === 204) return undefined as T
  const body: unknown = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(apiErrorMessage(body, resp.status))
  return body as T
}
