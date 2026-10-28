import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { ApiError } from './api'

/** Props de acessibilidade para o controle de um FieldRow. */
export function fieldA11y(id: string, error?: string) {
  return { id, 'aria-invalid': error ? true : undefined, 'aria-describedby': error ? `${id}-error` : undefined }
}

/**
 * Mostra no formulário o erro devolvido pela API: cada erro de campo ao lado do campo
 * (traduzindo nomes da API pelos de `fieldMap`) e o resto como erro geral.
 */
export function showServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fieldMap: Partial<Record<string, Path<T>>> = {},
  knownFields: readonly string[] = [],
): void {
  if (!(error instanceof ApiError)) {
    setError('root.server' as Path<T>, { message: 'Erro inesperado. Tente de novo.' })
    return
  }
  let shownOnField = false
  for (const [apiField, message] of Object.entries(error.fieldErrors)) {
    const field = fieldMap[apiField] ?? (knownFields.includes(apiField) ? (apiField as Path<T>) : undefined)
    if (field) {
      setError(field, { type: 'server', message })
      shownOnField = true
    }
  }
  if (!shownOnField) setError('root.server' as Path<T>, { message: error.message })
}
