import { useCallback, useEffect, useReducer, useRef } from 'react'
import { resultList } from '../api/accounting'
import { normalizeTrialRow, trialBalanceReducer, initialTrialBalance } from './trialBalanceReducer'
import type { TrialFilters } from './types'

type FetchBalance = (params: TrialFilters & { level: string }) => Promise<unknown>

export function useTrialBalance(level: string, fetchBalance: FetchBalance, scope = '') {
  const [state, dispatch] = useReducer(trialBalanceReducer, level, initialTrialBalance)
  const seq = useRef(0)
  const fetchRef = useRef(fetchBalance)
  fetchRef.current = fetchBalance

  useEffect(() => {
    dispatch({ type: 'level', level })
  }, [level])

  const load = useCallback((filters: TrialFilters, nextLevel: string) => {
    const id = ++seq.current
    dispatch({ type: 'loading', level: nextLevel })
    fetchRef.current({ ...filters, level: nextLevel }).then((result) => {
      if (id !== seq.current) return
      const rows = resultList(result).map((row: Record<string, unknown>) => normalizeTrialRow(row))
      dispatch({ type: 'loaded', rows, level: nextLevel })
    }).catch((err: Error) => {
      if (id !== seq.current) return
      dispatch({ type: 'failed', message: err?.message || 'خطا در بارگذاری تراز' })
    })
  }, [])

  useEffect(() => {
    load(state.filters, state.level)
  }, [load, state.filters, state.level, scope])

  const setFilters = useCallback((filters: TrialFilters) => {
    dispatch({ type: 'filters', filters })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: 'reset', level: state.level })
  }, [state.level])

  const reload = useCallback(() => {
    load(state.filters, state.level)
  }, [load, state.filters, state.level])

  return { state, setFilters, reset, reload }
}
