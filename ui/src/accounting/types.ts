export const SOURCE_MODULES = ['sales', 'warehouse', 'factory', 'manual'] as const

export type SourceModule = (typeof SOURCE_MODULES)[number]

export type SourceFilter = SourceModule | 'automatic' | ''

export type DocumentStatus = 'draft' | 'pending_review' | 'posted' | 'rejected' | 'void' | string

export type DocumentFilters = {
  status: string
  dateFrom: string
  dateTo: string
  documentNumber: string
  sourceModule: SourceFilter
}

export type AccountingDocument = {
  document_code: string
  document_number: number | string
  entry_date: string
  description: string
  status: DocumentStatus
  source_module: SourceModule | string
  source_label: string
  total_debit: number
  total_credit: number
  balanced: boolean
  line_count: number
  entry_type?: string
}

export type JournalLine = {
  id?: number | string
  description?: string
  debit: number
  credit: number
  general_account?: string
  subsidiary_account?: string
  detailed_account?: string
  account_name?: string
}

export type AccountingDocumentDetail = AccountingDocument & {
  lines: JournalLine[]
}

export type TrialFilters = {
  accountClass: string
  accountId: string
  subsidiaryId: string
  dateFrom: string
  dateTo: string
  approvedOnly: boolean
}

export type TrialRow = {
  code: string
  full_code: string
  name: string
  total_debit: number
  total_credit: number
  balance: number
}

export type BalanceSnapshot = {
  debit: number
  credit: number
  difference: number
  balanced: boolean
}

export type LineBalanceRow = JournalLine & {
  runningDebit: number
  runningCredit: number
  runningDifference: number
}
