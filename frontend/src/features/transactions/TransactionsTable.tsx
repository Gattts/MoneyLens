import { Amount } from '@/components/money-display'
import { RowActions } from '@/components/RowActions'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { paymentLabel } from '@/features/entries/entry-rules'
import { formatDate } from '@/lib/dates'
import type { Card as CreditCard, Category, Goal, Transaction } from '@/lib/types'

interface TransactionsTableProps {
  rows: Transaction[]
  categories: Category[]
  cards: CreditCard[]
  goals: Goal[]
  onEdit: (transaction: Transaction) => void
  onDelete: (transaction: Transaction) => void
}

function sumOf(rows: Transaction[], kind: Transaction['kind']) {
  return rows.filter((row) => row.kind === kind).reduce((sum, row) => sum + row.amount_cents, 0)
}

export function TransactionsTable({ rows, categories, cards, goals, onEdit, onDelete }: TransactionsTableProps) {
  const categoryById = new Map(categories.map((category) => [category.id, category]))
  const goalById = new Map(goals.map((goal) => [goal.id, goal]))
  return (
    <Card className="py-0">
      <CardContent className="px-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">Data</TableHead>
              <TableHead>Descrição</TableHead>
              <TableHead className="hidden md:table-cell">Categoria</TableHead>
              <TableHead className="hidden lg:table-cell">Pagamento</TableHead>
              <TableHead className="text-right">Valor</TableHead>
              <TableHead className="w-20">
                <span className="sr-only">Ações</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((transaction) => {
              const category = categoryById.get(transaction.category_id)
              const categoryText = category ? `${category.icon} ${category.name}`.trim() : '—'
              const goal = transaction.goal_id ? goalById.get(transaction.goal_id) : undefined
              return (
                <TableRow key={transaction.id}>
                  <TableCell className="tabular-nums">{formatDate(transaction.date)}</TableCell>
                  <TableCell className="max-w-64 whitespace-normal">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="font-medium">{transaction.description}</span>
                      {transaction.installment_total && (
                        <Badge variant="outline">
                          {transaction.installment_number}/{transaction.installment_total}
                        </Badge>
                      )}
                      {transaction.recurring_rule_id && <Badge variant="secondary">Fixa</Badge>}
                      {goal && <Badge variant="secondary">{`${goal.icon} ${goal.name}`.trim()}</Badge>}
                    </div>
                    <span className="text-xs text-muted-foreground md:hidden">{categoryText}</span>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">{categoryText}</TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {paymentLabel(transaction.payment_method, transaction.card_id, cards)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Amount cents={transaction.amount_cents} kind={transaction.kind} />
                  </TableCell>
                  <TableCell>
                    <RowActions
                      label={transaction.description}
                      onEdit={() => onEdit(transaction)}
                      onDelete={() => onDelete(transaction)}
                    />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={6} className="text-right text-sm">
                <span className="mr-4">
                  Receitas: <Amount cents={sumOf(rows, 'income')} kind="income" />
                </span>
                <span>
                  Despesas: <Amount cents={sumOf(rows, 'expense')} />
                </span>
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </CardContent>
    </Card>
  )
}
