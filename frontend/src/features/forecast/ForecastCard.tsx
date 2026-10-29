import { Link } from 'react-router'

import { SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatCents } from '@/lib/money'
import { useForecast } from '@/lib/queries'

import { SHOWN, SOURCE_LABELS, byAttention } from './forecast-labels'

/** Card do Painel: total previsto, teto e as categorias que merecem atenção (só no mês atual). */
export function ForecastCard() {
  const forecast = useForecast()
  const data = forecast.data
  return (
    <SectionCard
      title="Previsão do mês"
      description={data ? `Até o dia ${data.day}, pelo ${SOURCE_LABELS[data.source]}.` : undefined}
      action={
        <Button asChild variant="ghost" size="sm">
          <Link to="/previsao">Ver previsão</Link>
        </Button>
      }
    >
      {forecast.isError ? (
        <QueryError error={forecast.error} onRetry={() => void forecast.refetch()} />
      ) : !data ? (
        <LoadingBlock rows={2} />
      ) : data.categories.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem gastos para prever neste mês.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
            <span>
              Provável <span className="text-xl font-semibold tabular-nums">{formatCents(data.total.p50_cents)}</span>
            </span>
            <span className="text-muted-foreground">teto {formatCents(data.total.p90_cents)}</span>
            <span className="text-muted-foreground">gasto até agora {formatCents(data.total.spent_cents)}</span>
          </div>
          <ul className="flex flex-col divide-y">
            {[...data.categories]
              .sort(byAttention)
              .slice(0, SHOWN)
              .map((item) => (
                <li key={item.category_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <span className="min-w-0 truncate">
                    {item.icon} {item.name}
                  </span>
                  <span className="flex items-center gap-2 tabular-nums text-muted-foreground">
                    {formatCents(item.spent_cents)} de {formatCents(item.p50_cents)}–{formatCents(item.p90_cents)}
                    {item.alert && <Badge variant="destructive">Acima do normal</Badge>}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}
    </SectionCard>
  )
}
