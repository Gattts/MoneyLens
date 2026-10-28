import { toast } from 'sonner'

import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { api } from '@/lib/api'
import { useBudgetSettings, useRefreshData } from '@/lib/queries'
import type { BudgetSettings } from '@/lib/types'

import { BudgetSettingsForm } from './BudgetSettingsForm'

export function SettingsPage() {
  const budget = useBudgetSettings()
  const refresh = useRefreshData()

  async function save(settings: BudgetSettings) {
    await api.budget.update(settings)
    toast.success('Divisão do orçamento salva.')
    void refresh()
  }

  return (
    <>
      <PageHeader title="Configurações" />
      <SectionCard title="Divisão da renda" description="Quanto da renda vai para cada grupo. O clássico é 50/30/20.">
        {budget.isError ? (
          <QueryError error={budget.error} onRetry={() => void budget.refetch()} />
        ) : budget.isPending ? (
          <LoadingBlock rows={2} />
        ) : (
          <BudgetSettingsForm
            key={`${budget.data.needs_pct}-${budget.data.wants_pct}-${budget.data.savings_pct}`}
            initial={budget.data}
            onSubmit={save}
          />
        )}
      </SectionCard>
      <SectionCard title="Como o termômetro funciona">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>Compara o gasto com necessidades e desejos com a renda prevista do mês.</li>
          <li>
            <strong className="text-foreground">Controlado</strong>: o gasto cabe no seu plano (por exemplo, até 80% da
            renda no 50/30/20).
          </li>
          <li>
            <strong className="text-foreground">Atenção</strong>: passou do plano, mas ainda cabe na renda.
          </li>
          <li>
            <strong className="text-foreground">Negativo</strong>: gastou mais do que ganhou.
          </li>
          <li>Poupança não conta como gasto: guardar dinheiro nunca piora o termômetro.</li>
        </ul>
      </SectionCard>
      <SectionCard title="Senha">
        <p className="text-sm text-muted-foreground">
          Para trocar a senha, rode no computador onde o sistema está instalado:{' '}
          <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">uv run financeiro set-password</code>. As
          sessões abertas em outros navegadores são encerradas.
        </p>
      </SectionCard>
    </>
  )
}
