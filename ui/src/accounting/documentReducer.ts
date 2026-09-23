import { linesBalance } from './balance'
import type {
  AccountingDocument,
  AccountingDocumentDetail,
  BalanceSnapshot,
  DocumentFilters,
  JournalLine,
  LineBalanceRow,
} from './types'
import { emptySnapshot } from './balance'

export const DEFAULT_DOCUMENT_FILTERS: DocumentFilters = {
  status: '',
  dateFrom: '',
  dateTo: '',
  documentNumber: '',
  sourceModule: 'automatic',
}

export const DOCUMENT_PAGE_SIZE = 20

export type DocumentBoardState = {
  draft: DocumentFilters
  applied: DocumentFilters
  page: number
  rows: AccountingDocument[]
  total: number
  loading: boolean
  error: string
  selectedCode: string
  detail: AccountingDocumentDetail | null
  detailLoading: boolean
  lineRows: LineBalanceRow[]
  lineTotals: BalanceSnapshot
  pageTotals: BalanceSnapshot
}

export const initialDocumentBoard = (): DocumentBoardState => ({
  draft: { ...DEFAULT_DOCUMENT_FILTERS },
  applied: { ...DEFAULT_DOCUMENT_FILTERS },
  page: 1,
  rows: [],
  total: 0,
  loading: false,
  error: '',
  selectedCode: '',
  detail: null,
  detailLoading: false,
  lineRows: [],
  lineTotals: emptySnapshot(),
  pageTotals: emptySnapshot(),
})

export type DocumentBoardAction =
  | { type: 'patch'; patch: Partial<DocumentFilters> }
  | { type: 'apply' }
  | { type: 'reset' }
  | { type: 'page'; page: number }
  | { type: 'loading' }
  | { type: 'loaded'; rows: AccountingDocument[]; total: number; pageTotals: BalanceSnapshot }
  | { type: 'failed'; message: string }
  | { type: 'select'; code: string }
  | { type: 'detail-loading' }
  | { type: 'detail'; document: AccountingDocumentDetail; lines: JournalLine[] }
  | { type: 'detail-clear' }

function pageTotals(rows: AccountingDocument[]): BalanceSnapshot {
  const debit = rows.reduce((sum, row) => sum + Number(row.total_debit || 0), 0)
  const credit = rows.reduce((sum, row) => sum + Number(row.total_credit || 0), 0)
  const difference = debit - credit
  return { debit, credit, difference, balanced: difference === 0 }
}

export function documentBoardReducer(state: DocumentBoardState, action: DocumentBoardAction): DocumentBoardState {
  switch (action.type) {
    case 'patch':
      return { ...state, draft: { ...state.draft, ...action.patch } }
    case 'apply':
      return { ...state, applied: { ...state.draft }, page: 1, error: '' }
    case 'reset':
      return {
        ...state,
        draft: { ...DEFAULT_DOCUMENT_FILTERS },
        applied: { ...DEFAULT_DOCUMENT_FILTERS },
        page: 1,
        selectedCode: '',
        detail: null,
        lineRows: [],
        lineTotals: emptySnapshot(),
        error: '',
      }
    case 'page':
      return { ...state, page: action.page }
    case 'loading':
      return { ...state, loading: true, error: '' }
    case 'loaded':
      return {
        ...state,
        loading: false,
        rows: action.rows,
        total: action.total,
        pageTotals: action.pageTotals,
        error: '',
      }
    case 'failed':
      return { ...state, loading: false, rows: [], total: 0, pageTotals: emptySnapshot(), error: action.message }
    case 'select':
      return { ...state, selectedCode: action.code }
    case 'detail-loading':
      return { ...state, detailLoading: true }
    case 'detail': {
      const balanced = linesBalance(action.lines)
      return {
        ...state,
        detailLoading: false,
        detail: action.document,
        lineRows: balanced.rows,
        lineTotals: balanced.totals,
      }
    }
    case 'detail-clear':
      return {
        ...state,
        detail: null,
        detailLoading: false,
        lineRows: [],
        lineTotals: emptySnapshot(),
      }
    default:
      return state
  }
}

export { pageTotals }
