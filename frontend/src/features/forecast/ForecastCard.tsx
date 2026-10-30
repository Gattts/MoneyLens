import { Link } from 'react-router'

import { SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatCents } from '@/lib/money'
import { useForecast } from '@/lib/queries'

import { MIN_HISTORY_MONTHS } from './forecast-labels'

/** Resumo da previsão no Painel (só no mês atual): provável, gasto, máximo provável e as categorias em alerta. */
export function ForecastCard() {
  const forecast = useForecast()
  const data = forecast.data
  const alerts = data?.categories.filter((item) => item.alert).length ?? 0
  return (
    <SectionCard
      title="Previsão do mês"
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
      ) : data.history_months < MIN_HISTORY_MONTHS ? (
        <div className="flex flex-col gap-1 text-sm">
          <p className="font-medium">Dados insuficientes para prever.</p>
          <p className="text-muted-foreground">
            A previsão começa com {MIN_HISTORY_MONTHS} meses fechados de histórico; você tem {data.history_months}.
          </p>
        </div>
      ) : data.categories.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem gastos para prever neste mês.</p>
      ) : (
        <div className="flex flex-col gap-2 text-sm">
          <p className="flex items-baseline gap-2">
            <span className="text-muted-foreground">Provável</span>
            <span className="text-xl font-semibold tabular-nums">{formatCents(data.total.p50_cents)}</span>
          </p>
          <p className="tabular-nums text-muted-foreground">
            Gasto até agora {formatCents(data.total.spent_cents)} · máximo provável {formatCents(data.total.p90_cents)}
          </p>
          {alerts > 0 && (
            <Badge variant="destructive" className="w-fit">
              {alerts === 1 ? '1 categoria acima do normal' : `${alerts} categorias acima do normal`}
            </Badge>
          )}
        </div>
      )}
    </SectionCard>
  )
}
