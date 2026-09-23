import { useEffect, useReducer, useRef } from 'react'
import { resultList } from '../api/accounting'
import { money } from './balance'
import {
  DOCUMENT_PAGE_SIZE,
  documentBoardReducer,
  initialDocumentBoard,
  pageTotals,
} from './documentReducer'
import type { AccountingDocument, AccountingDocumentDetail, JournalLine } from './types'

type DocumentsApi = {
  listDocuments: (opts: Record<string, string | number>) => Promise<unknown>
  getDocument: (code: string) => Promise<unknown>
}

function asDocument(row: Record<string, unknown>): AccountingDocument {
  const debit = money(row.total_debit)
  const credit = money(row.total_credit)
  return {
    document_code: String(row.document_code || ''),
    document_number: (row.document_number as number | string) ?? '',
    entry_date: String(row.entry_date || row.date || ''),
    description: String(row.description || ''),
    status: String(row.status || ''),
    source_module: String(row.source_module || 'manual'),
    source_label: String(row.source_label || ''),
    total_debit: debit,
    total_credit: credit,
    balanced: row.balanced == null ? debit === credit : Boolean(row.balanced),
    line_count: money(row.line_count),
    entry_type: row.entry_type ? String(row.entry_type) : undefined,
  }
}

function asLines(payload: Record<string, unknown>): JournalLine[] {
  const lines = Array.isArray(payload.lines) ? payload.lines : []
  return lines.map((line) => {
    const row = line as Record<string, unknown>
    return {
      id: row.id as number | string | undefined,
      description: String(row.description || ''),
      debit: money(row.debit),
      credit: money(row.credit),
      general_account: String(row.general_account || row.account_name || ''),
      subsidiary_account: String(row.subsidiary_account || ''),
      detailed_account: String(row.detailed_account || ''),
      account_name: String(row.account_name || ''),
    }
  })
}

export function useDocumentBoard(api: DocumentsApi, reloadToken = 0) {
  const [state, dispatch] = useReducer(documentBoardReducer, undefined, initialDocumentBoard)
  const listSeq = useRef(0)
  const detailSeq = useRef(0)

  useEffect(() => {
    const seq = ++listSeq.current
    dispatch({ type: 'loading' })
    const { applied, page } = state
    api.listDocuments({
      status: applied.status,
      dateFrom: applied.dateFrom,
      dateTo: applied.dateTo,
      documentNumber: applied.documentNumber,
      sourceModule: applied.sourceModule,
      offset: (page - 1) * DOCUMENT_PAGE_SIZE,
      limit: DOCUMENT_PAGE_SIZE,
    }).then((result) => {
      if (seq !== listSeq.current) return
      const payload = (result || {}) as { total?: number }
      const rows = resultList(result).map((row: Record<string, unknown>) => asDocument(row))
      dispatch({
        type: 'loaded',
        rows,
        total: Number(payload.total ?? rows.length),
        pageTotals: pageTotals(rows),
      })
    }).catch((err: Error) => {
      if (seq !== listSeq.current) return
      dispatch({ type: 'failed', message: err?.message || 'خطا در بارگذاری اسناد' })
    })
    // applied و page از state خوانده می‌شوند؛ وابستگی صریح همان‌هاست.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, state.applied, state.page, reloadToken])

  useEffect(() => {
    if (!state.selectedCode) {
      dispatch({ type: 'detail-clear' })
      return
    }
    const seq = ++detailSeq.current
    const code = state.selectedCode
    dispatch({ type: 'detail-loading' })
    api.getDocument(code).then((result) => {
      if (seq !== detailSeq.current) return
      const payload = (result || {}) as Record<string, unknown>
      const document = asDocument({ ...payload, document_code: payload.document_code || code })
      dispatch({ type: 'detail', document: { ...document, lines: asLines(payload) }, lines: asLines(payload) })
    }).catch(() => {
      if (seq !== detailSeq.current) return
      dispatch({ type: 'detail-clear' })
    })
  }, [api, state.selectedCode])

  return { state, dispatch, pageSize: DOCUMENT_PAGE_SIZE }
}

export type { AccountingDocumentDetail }
