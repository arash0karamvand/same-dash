import { EmptyState } from '../ui'
import { AccountingDataPanel } from './AccountingERP'
import LiveTBalance from './LiveTBalance'
import { fromLegacy } from '../../styles/tw'
import { formatRial } from '../../utils/format'

export default function ProfitCenterReport({ data = [], loading = false }) {
  if (loading) {
    return <div className={fromLegacy("loading")}>در حال بارگذاری گزارش…</div>
  }

  if (!Array.isArray(data) || data.length === 0) {
    return <EmptyState text="شعبه فعالی به‌عنوان مرکز درآمد نیست." />
  }

  const totals = data.reduce((acc, row) => ({
    revenue: acc.revenue + Number(row.revenue || 0),
    expense: acc.expense + Number(row.expense || 0),
  }), { revenue: 0, expense: 0 })

  return (
    <AccountingDataPanel title="سود و زیان مراکز درآمد" subtitle={`${data.length.toLocaleString('fa-IR')} مرکز`}>
      <div className="acct-card-stack is-compact">
        <div className="acct-strip-head acct-strip--4" aria-hidden>
          <span>شعبه</span>
          <span className="is-num">درآمد</span>
          <span className="is-num">هزینه</span>
          <span className="is-num">سود</span>
        </div>
        {data.map((row, idx) => {
          const profit = (row.revenue || 0) - (row.expense || 0)
          return (
            <div key={row.branch_id || idx} className="acct-strip acct-strip--4">
              <span style={{ fontWeight: 600 }}>{row.branch_name || row.label || '-'}</span>
              <strong className="acct-number acct-credit">{formatRial(row.revenue || 0)}</strong>
              <strong className="acct-number acct-debit">{formatRial(row.expense || 0)}</strong>
              <strong className={`acct-number ${profit >= 0 ? 'acct-credit' : 'acct-debit'}`}>{formatRial(profit)}</strong>
            </div>
          )
        })}
        <LiveTBalance debit={totals.expense} credit={totals.revenue} label="تراز آزمایشی لحظه‌ای مراکز درآمد" compact />
      </div>
    </AccountingDataPanel>
  )
}
