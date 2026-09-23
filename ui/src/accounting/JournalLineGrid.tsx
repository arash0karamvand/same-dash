import LiveTBalance from '../components/accounting/LiveTBalance'
import { formatRial } from '../utils/format'
import type { AccountingDocumentDetail, LineBalanceRow, BalanceSnapshot } from './types'
import { sourceClass } from './sourceModules'

type Props = {
  document: AccountingDocumentDetail | null
  rows: LineBalanceRow[]
  totals: BalanceSnapshot
  loading: boolean
}

export default function JournalLineGrid({ document, rows, totals, loading }: Props) {
  if (!document && !loading) return null
  return (
    <section className="acct-line-panel acct-glass-panel">
      <header className="acct-line-panel-head">
        <div>
          <h3>ردیف‌های سند {document?.document_number || ''}</h3>
          <p>{document?.description || 'جزئیات سند انتخاب‌شده'}</p>
        </div>
        {document && (
          <span className={sourceClass(document.source_module)}>{document.source_label}</span>
        )}
      </header>
      {loading ? (
        <div className="acct-inline-muted">در حال خواندن ردیف‌ها…</div>
      ) : (
        <div className="acct-card-stack is-compact">
          {rows.map((line, index) => (
            <div key={line.id ?? index} className="acct-line-card">
              <div>
                {[line.general_account, line.subsidiary_account, line.detailed_account]
                  .filter(Boolean)
                  .join(' / ') || line.account_name || '—'}
              </div>
              <div>{line.description || '—'}</div>
              <strong className={`acct-number${line.debit ? ' acct-debit' : ''}`}>
                {line.debit ? formatRial(line.debit) : '—'}
              </strong>
              <strong className={`acct-number${line.credit ? ' acct-credit' : ''}`}>
                {line.credit ? formatRial(line.credit) : '—'}
              </strong>
              <strong className="acct-number">{formatRial(line.runningDifference)}</strong>
            </div>
          ))}
          <LiveTBalance
            debit={totals.debit}
            credit={totals.credit}
            label="تراز آزمایشی لحظه‌ای سند"
            compact
          />
        </div>
      )}
    </section>
  )
}
