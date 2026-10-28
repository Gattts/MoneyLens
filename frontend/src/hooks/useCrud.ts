import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { useRefreshData } from '@/lib/queries'

/** Estado do diálogo de criar/editar: aberto ou não, e qual item está sendo editado. */
export function useEditor<T>() {
  const [state, setState] = useState<{ open: boolean; item?: T }>({ open: false })
  return {
    open: state.open,
    item: state.item,
    create: () => setState({ open: true }),
    edit: (item: T) => setState({ open: true, item }),
    setOpen: (open: boolean) => setState((previous) => ({ ...previous, open })),
  }
}

/** Pergunta antes de excluir e mostra o resultado (inclusive o motivo, se a API recusar). */
export function useRemove<T extends { id: number }>(remove: (id: number) => Promise<void>, successMessage: string) {
  const refresh = useRefreshData()
  const [target, setTarget] = useState<T | null>(null)
  const mutation = useMutation({
    mutationFn: (item: T) => remove(item.id),
    onSuccess: () => {
      toast.success(successMessage)
      void refresh()
    },
    onError: (error) => toast.error(error.message),
    onSettled: () => setTarget(null),
  })
  return {
    target,
    ask: (item: T) => setTarget(item),
    dismiss: () => setTarget(null),
    // Devolve a Promise para o ConfirmDialog travar até o fim (erros já viram aviso no onError).
    confirm: () => (target ? mutation.mutateAsync(target).catch(() => undefined) : undefined),
    pending: mutation.isPending,
  }
}

/** Salva e avisa; usado para ações de um clique, como arquivar. */
export function useQuickAction<TArg>(action: (arg: TArg) => Promise<unknown>, successMessage: (arg: TArg) => string) {
  const refresh = useRefreshData()
  // `isPending` chega tarde para desabilitar o botão no 2º clique; a ref trava na hora.
  const running = useRef(false)
  const mutation = useMutation({
    mutationFn: action,
    onSuccess: (_result, arg) => {
      toast.success(successMessage(arg))
      void refresh()
    },
    onError: (error) => toast.error(error.message),
    onSettled: () => {
      running.current = false
    },
  })
  return {
    ...mutation,
    mutate: (arg: TArg) => {
      if (running.current) return
      running.current = true
      mutation.mutate(arg)
    },
  }
}
