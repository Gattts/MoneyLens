import { Link } from 'react-router'

import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { formatCents } from '@/lib/money'
import { useCards, useInvoiceImports } from '@/lib/queries'
import type { Card, InvoiceImport } from '@/lib/types'

import { importHeading, importName, isStatement } from './import-labels'
import { ImportForm } from './ImportForm'
import { RulesSection } from './RulesSection'

function ImportRow({ item, cards }: { item: InvoiceImport; cards: Card[] }) {
  const card = cards.find((candidate) => candidate.id === item.card_id)
  const name = isStatement(item) ? importName(item) : (card?.name ?? 'Cartão')
  const total = isStatement(item) ? `saídas ${formatCents(item.total_cents)}` : formatCents(item.total_cents)
  return (
    <li>
      <Link
        to={`/faturas/${item.id}`}
        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 hover:bg-muted"
      >
        <span>
          <span className="font-medium">{importHeading(item)}</span>
          <span className="block text-sm text-muted-foreground">
            {name} · {item.line_count} linhas · {total}
          </span>
        </span>
        <span className="flex flex-wrap gap-2">
          {item.pending_count > 0 && <Badge variant="destructive">{item.pending_count} em standby</Badge>}
          <Badge variant="secondary">{item.confirmed_at ? 'Confirmada' : 'Aguardando confirmação'}</Badge>
        </span>
      </Link>
    </li>
  )
}

export function InvoicesPage() {
  const cards = useCards()
  const imports = useInvoiceImports()
  return (
    <>
      <PageHeader
        title="Importar fatura ou extrato"
        description="Importe a fatura do cartão ou o extrato da conta em PDF e revise o que foi reconhecido."
      />
      <SectionCard
        title="Importar arquivo"
        description="Por enquanto: fatura do Inter e extratos do Nubank e do PicPay. O arquivo é lido e descartado; nada dele fica guardado."
      >
        {cards.isError ? (
          <QueryError error={cards.error} onRetry={() => void cards.refetch()} />
        ) : cards.isPending ? (
          <LoadingBlock rows={2} />
        ) : (
          <ImportForm cards={cards.data} />
        )}
      </SectionCard>
      <SectionCard title="Importações">
        {imports.isError ? (
          <QueryError error={imports.error} onRetry={() => void imports.refetch()} />
        ) : imports.isPending ? (
          <LoadingBlock rows={2} />
        ) : imports.data.imports.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nada importado ainda.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {imports.data.imports.map((item) => (
              <ImportRow key={item.id} item={item} cards={cards.data ?? []} />
            ))}
          </ul>
        )}
      </SectionCard>
      <RulesSection />
    </>
  )
}
