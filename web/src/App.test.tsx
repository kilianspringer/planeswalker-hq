import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Health } from './lib/health'

const SHA = '0123456789abcdef0123456789abcdef01234567'

function renderApp() {
  // No retries: a failing request must show up at once, not after three attempts.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

function answer(status: number, body: Health | string) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('shows version, migration and database state', async () => {
    answer(200, {
      status: 'ok',
      version: SHA,
      database: 'ok',
      migration: { version: 1, name: 'init' },
    })

    renderApp()

    expect(await screen.findByText('0123456')).toBeInTheDocument()
    expect(screen.getByText('0001 · init')).toBeInTheDocument()
    expect(screen.getByText('verbunden')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Planeswalker HQ' })).toBeInTheDocument()
  })

  it('shows an unreachable database when the API answers 503', async () => {
    answer(503, { status: 'error', version: SHA, database: 'unreachable', migration: null })

    renderApp()

    expect(await screen.findByText('nicht erreichbar')).toBeInTheDocument()
    expect(screen.getByText('erreichbar')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('shows an unreachable API when the request fails', async () => {
    answer(500, 'Internal Server Error')

    renderApp()

    expect(await screen.findByText('nicht erreichbar')).toBeInTheDocument()
    expect(screen.queryByText('Datenbank')).not.toBeInTheDocument()
  })
})
