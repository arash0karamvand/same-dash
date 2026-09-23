import { money, trialSnapshot } from './balance'
import type { BalanceSnapshot, TrialFilters, TrialRow } from './types'
import { emptySnapshot } from './balance'

export const INITIAL_TRIAL_FILTERS: TrialFilters = {
  accountClass: '',
  accountId: '',
  subsidiaryId: '',
  dateFrom: '',
  dateTo: '',
  approvedOnly: true,
}

export type TrialBalanceState = {
  filters: TrialFilters
  level: string
  rows: TrialRow[]
  totals: BalanceSnapshot
  loading: boolean
  error: string
}

export const initialTrialBalance = (level = 'general'): TrialBalanceState => ({
  filters: { ...INITIAL_TRIAL_FILTERS },
  level,
  rows: [],
  totals: emptySnapshot(),
  loading: false,
  error: '',
})

export type TrialBalanceAction =
  | { type: 'filters'; filters: TrialFilters }
  | { type: 'level'; level: string }
  | { type: 'loading'; level: string }
  | { type: 'loaded'; rows: TrialRow[]; level: string }
  | { type: 'failed'; message: string }
  | { type: 'reset'; level: string }

export function normalizeTrialRow(row: Record<string, unknown>): TrialRow {
  const debit = money(row.total_debit ?? row.turnover_debit)
  const credit = money(row.total_credit ?? row.turnover_credit)
  const balance = row.balance == null
    ? money(row.balance_debit) - money(row.balance_credit)
    : money(row.balance)
  return {
    code: String(row.code || row.account_code || ''),
    full_code: String(row.full_code || row.account_code || row.code || ''),
    name: String(row.name || row.account_name || ''),
    total_debit: debit,
    total_credit: credit,
    balance,
  }
}

export function trialBalanceReducer(state: TrialBalanceState, action: TrialBalanceAction): TrialBalanceState {
  switch (action.type) {
    case 'filters': {
      const next = { ...action.filters }
      if (next.accountId !== state.filters.accountId) next.subsidiaryId = ''
      return { ...state, filters: next }
    }
    case 'level':
      return action.level === state.level ? state : { ...state, level: action.level, rows: [], totals: emptySnapshot() }
    case 'loading':
      return {
        ...state,
        loading: true,
        error: '',
        rows: action.level === state.level ? state.rows : [],
        totals: action.level === state.level ? state.totals : emptySnapshot(),
      }
    case 'loaded':
      if (action.level !== state.level) return { ...state, loading: false }
      return { ...state, loading: false, rows: action.rows, totals: trialSnapshot(action.rows), error: '' }
    case 'failed':
      return { ...state, loading: false, rows: [], totals: emptySnapshot(), error: action.message }
    case 'reset':
      return initialTrialBalance(action.level)
    default:
      return state
  }
}
