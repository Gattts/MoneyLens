import { createContext, useContext } from 'react'

export const AlertsPanelContext = createContext<{ open: () => void }>({ open: () => {} })

/** Abre o painel lateral de alertas (o sino e o "Ver todos" do Painel). */
export const useAlertsPanel = () => useContext(AlertsPanelContext)
