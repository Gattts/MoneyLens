import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatMonthLabel } from '@/lib/dates'
import { formatCents } from '@/lib/money'
import { useForecast, useForecastModels } from '@/lib/queries'
import type { ForecastModelInfo } from '@/lib/types'

import { SOURCE_LABELS, byAttention } from './forecast-labels'

const NO_MODEL = 'Usando o modelo base. Rode `financeiro treinar` com pelo menos 2 meses fechados.'

function MonthTable() {
  const forecast = useForecast()
  if (forecast.isError) return <QueryError error={forecast.error} onRetry={() => void forecast.refetch()} />
  if (!forecast.data) return <LoadingBlock rows={4} />
  const data = forecast.data
  if (data.categories.length === 0) return <p className="text-sm text-muted-foreground">Sem gastos para prever.</p>
  return (
    <div className="overflow-x-auto">
      <p className="mb-3 text-sm text-muted-foreground">
        Até o dia {data.day}, pelo {SOURCE_LABELS[data.source]}. O máximo provável é o valor que o mês não deve passar
        em 9 de cada 10 vezes. Pelo mês de pagamento: compras no cartão contam no mês em que a fatura vence, e o
        comprometido já inclui faturas, parcelas e fixas do mês.
      </p>
      <table className="w-full min-w-[34rem] text-sm">
        <thead className="text-left text-muted-foreground">
          <tr>
            <th className="py-2 font-medium">Categoria</th>
            <th className="py-2 font-medium">Comprometido</th>
            <th className="py-2 font-medium">Provável</th>
            <th className="py-2 font-medium">Máximo provável</th>
            <th className="py-2 font-medium">Estatística</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody className="divide-y tabular-nums">
          {[...data.categories].sort(byAttention).map((item) => (
            <tr key={item.category_id}>
              <td className="py-2">
                {item.icon} {item.name}
              </td>
              <td className="py-2">{formatCents(item.committed_cents)}</td>
              <td className="py-2">{formatCents(item.p50_cents)}</td>
              <td className="py-2">{formatCents(item.p90_cents)}</td>
              <td className="py-2">{formatCents(item.baseline_cents)}</td>
              <td className="py-2">{item.alert && <Badge variant="destructive">Acima do normal</Badge>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ModelItem({ model }: { model: ForecastModelInfo }) {
  const { mae_model_cents: modelError, mae_baseline_cents: baselineError, coverage_p90: coverage } = model.metrics
  return (
    <li className="flex flex-col gap-1 rounded-lg border p-3 text-sm">
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Versão {model.version}</span>
        {model.active && <Badge variant="secondary">Em uso</Badge>}
        <span className="text-muted-foreground">
          treinada em {formatDate(model.trained_at.slice(0, 10))}, com dados até {formatMonthLabel(model.trained_until)}
        </span>
      </span>
      <span className="flex flex-wrap gap-x-4 text-muted-foreground">
        <span>{`Erro médio do modelo: ${formatCents(modelError)}`}</span>
        <span>{`Da estatística: ${formatCents(baselineError)}`}</span>
        <span>{`O máximo provável cobriu ${Math.round(coverage * 100)}% dos casos`}</span>
      </span>
    </li>
  )
}

function ModelHistory() {
  const models = useForecastModels()
  if (models.isError) return <QueryError error={models.error} onRetry={() => void models.refetch()} />
  if (!models.data) return <LoadingBlock rows={2} />
  if (models.data.length === 0) return <p className="text-sm text-muted-foreground">{NO_MODEL}</p>
  return (
    <ul className="flex flex-col gap-2">
      {models.data.map((model) => (
        <ModelItem key={model.version} model={model} />
      ))}
    </ul>
  )
}

/** Previsão do mês por categoria e o histórico de treinos do modelo (a vitrine do ML). */
export function ForecastPage() {
  return (
    <>
      <PageHeader
        title="Previsão"
        description="Quanto você deve gastar até o fim do mês, por categoria, e como o modelo está aprendendo."
      />
      <SectionCard title="Este mês">
        <MonthTable />
      </SectionCard>
      <SectionCard
        title="Treinos do modelo"
        description="Cada treino testa o modelo no último mês fechado e compara o erro com o da estatística."
      >
        <ModelHistory />
      </SectionCard>
    </>
  )
}
