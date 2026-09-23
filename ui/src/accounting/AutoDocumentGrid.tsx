import WorkflowStatusBadge from '../components/accounting/WorkflowStatusBadge'
import LiveTBalance from '../components/accounting/LiveTBalance'
import Icon from '../components/icons/Icon'
import { fromLegacy } from '../styles/tw'
import { formatDate, formatRial } from '../utils/format'
import { sourceClass } from './sourceModules'
import type { AccountingDocument, BalanceSnapshot } from './types'

type Props = {
  rows: AccountingDocument[]
  loading: boolean
  error: string
  selectedCode: string
  compact: boolean
  totals: BalanceSnapshot
  onSelect: (code: string) => void
  onOpen: (doc: AccountingDocument) => void
  onDelete: (code: string) => void
}

export default function AutoDocumentGrid({
  rows,
  loading,
  error,
  selectedCode,
  compact,
  totals,
  onSelect,
  onOpen,
  onDelete,
}: Props) {
  if (loading) return <div className={fromLegacy('loading')}>در حال بارگذاری اسناد…</div>
  if (error) return <div className="acct-inline-error">{error}</div>
  if (rows.length === 0) {
    return <div className={fromLegacy('empty')}>سندی با این فیلتر پیدا نشد.</div>
  }

  return (
    <div className={`acct-card-stack${compact ? ' is-compact' : ''}`}>
      {rows.map((doc) => {
        const selected = selectedCode === doc.document_code
        return (
          <article
            key={doc.document_code}
            className={`acct-doc-card${selected ? ' is-selected' : ''}${doc.balanced ? '' : ' is-off'}`}
            role="button"
            tabIndex={0}
            aria-pressed={selected}
            onClick={() => onSelect(doc.document_code)}
            onDoubleClick={() => onOpen(doc)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                onOpen(doc)
              }
              if (event.key === ' ') {
                event.preventDefault()
                onSelect(doc.document_code)
              }
            }}
          >
            <div className="acct-doc-id">
              <strong className="acct-number">{doc.document_number || '—'}</strong>
              <small>{formatDate(doc.entry_date)}</small>
            </div>
            <div className="acct-doc-copy">
              <span className={sourceClass(doc.source_module)}>
                {doc.source_label || doc.source_module}
              </span>
              <p title={doc.description || ''}>{doc.description || '—'}</p>
            </div>
            <div className="acct-doc-amounts">
              <div>
                <span>بدهکار</span>
                <strong className="acct-number acct-debit">{formatRial(doc.total_debit)}</strong>
              </div>
              <div>
                <span>بستانکار</span>
                <strong className="acct-number acct-credit">{formatRial(doc.total_credit)}</strong>
              </div>
            </div>
            <div className="acct-doc-actions">
              <span className={doc.balanced ? 'acct-balance is-ok' : 'acct-balance is-off'}>
                {doc.balanced ? 'متعادل' : 'اختلاف'}
              </span>
              <WorkflowStatusBadge status={doc.status} />
              <button
                type="button"
                className={fromLegacy('acct-table-action')}
                aria-label="مشاهده سند"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation()
                  onOpen(doc)
                }}
              >
                <Icon name="eye" size={18} />
              </button>
              {doc.status === 'draft' && (
                <button
                  type="button"
                  className={fromLegacy('acct-table-action is-danger')}
                  aria-label="حذف سند"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation()
                    onDelete(doc.document_code)
                  }}
                >
                    <Icon name="trash" size={18} />
                </button>
              )}
            </div>
          </article>
        )
      })}
      <LiveTBalance
        debit={totals.debit}
        credit={totals.credit}
        label="تراز آزمایشی لحظه‌ای صفحه"
        compact={compact}
      />
    </div>
  )
}
