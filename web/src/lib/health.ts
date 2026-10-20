import { useQuery } from '@tanstack/react-query'

/** Shape of GET /health, see api/app/routes/health.py. */
export type Health = {
  status: 'ok' | 'error'
  version: string
  database: 'ok' | 'unreachable'
  migration: { version: number; name: string } | null
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch('/health')
  // 503 still carries a Health body: the API is up, the database is not.
  if (!response.ok && response.status !== 503) {
    throw new Error(`GET /health answered ${response.status}`)
  }
  return (await response.json()) as Health
}

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })
}
