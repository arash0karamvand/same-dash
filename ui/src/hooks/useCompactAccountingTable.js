import { usePersistedState } from './usePersistedState'

export function useCompactAccountingTable() {
  const [compactView] = usePersistedState('accounting-table-compact', false)
  return compactView
}
