import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { type Health, useHealth } from '@/lib/health'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  )
}

function StatusBadge({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return <Badge variant={ok ? 'secondary' : 'destructive'}>{children}</Badge>
}

function HealthDetails({ health }: { health: Health }) {
  const { migration } = health
  return (
    <dl className="divide-y">
      <Row label="API">
        <StatusBadge ok>erreichbar</StatusBadge>
      </Row>
      <Row label="Datenbank">
        <StatusBadge ok={health.database === 'ok'}>
          {health.database === 'ok' ? 'verbunden' : 'nicht erreichbar'}
        </StatusBadge>
      </Row>
      <Row label="Migration">
        {migration ? `${String(migration.version).padStart(4, '0')} · ${migration.name}` : '—'}
      </Row>
      <Row label="Version">
        <code title={health.version}>{health.version.slice(0, 7)}</code>
      </Row>
    </dl>
  )
}

export default function App() {
  const { data, error, isPending } = useHealth()

  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center gap-6 p-4">
      <h1 className="font-heading text-3xl font-semibold tracking-tight">Planeswalker HQ</h1>
      <Card>
        <CardHeader>
          <CardTitle>Systemstatus</CardTitle>
          <CardDescription>Was gerade läuft</CardDescription>
        </CardHeader>
        <CardContent>
          {isPending && <p className="text-muted-foreground">Lade …</p>}
          {error && (
            <dl>
              <Row label="API">
                <StatusBadge ok={false}>nicht erreichbar</StatusBadge>
              </Row>
            </dl>
          )}
          {data && <HealthDetails health={data} />}
        </CardContent>
      </Card>
    </main>
  )
}
