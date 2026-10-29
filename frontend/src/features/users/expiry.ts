/** Data de validade do convite como DD/MM (o que a pessoa precisa saber para não perder o prazo). */
export function expiryLabel(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) : ''
}
