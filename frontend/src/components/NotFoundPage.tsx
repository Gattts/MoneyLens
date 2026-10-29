import { Link } from 'react-router'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Página não encontrada" description="O endereço digitado não existe." />
      <Button asChild className="self-start">
        <Link to="/">Voltar ao painel</Link>
      </Button>
    </>
  )
}
