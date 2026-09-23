import { useMemo } from 'react'
import { Card, EmptyState } from '../ui'
import { formatRial } from '../../utils/format'
import Icon from '../icons/Icon'
import { useCompactAccountingTable } from '../../hooks/useCompactAccountingTable'
import LiveTBalance from './LiveTBalance'

export default function TrialBalanceView({ data = [], level = 'general', loading = false, onRowClick }) {
  const compactView = useCompactAccountingTable()

  const totals = useMemo(() => {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return { debit: 0, credit: 0, balance: 0 }
    }
    return data.reduce(
      (acc, row) => ({
        debit: acc.debit + (row.total_debit || 0),
        credit: acc.credit + (row.total_credit || 0),
        balance: acc.balance + Math.abs(row.balance || 0),
      }),
      { debit: 0, credit: 0, balance: 0 },
    )
  }, [data])

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '3rem 2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <Icon name="hourglass" size={40} />
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>در حال بارگذاری داده‌های مالی...</p>
        </div>
      </Card>
    )
  }

  if (!data || !Array.isArray(data) || data.length === 0) {
    return <EmptyState text="داده‌ای برای نمایش وجود ندارد. فیلترها را تنظیم کرده یا تاریخ دیگری انتخاب کنید." />
  }

  const isClickable = typeof onRowClick === 'function'
  const showFullCode = level !== 'general'

  return (
    <div className={`acct-card-stack${compactView ? ' is-compact' : ''}`} style={{ marginTop: 'var(--acct-space-md)' }}>
      <div className="acct-strip-head" aria-hidden>
        <span>کد</span>
        <span>نام حساب</span>
        <span>{showFullCode ? 'کد کامل' : ''}</span>
        <span className="is-num">بدهکار</span>
        <span className="is-num">بستانکار</span>
        <span className="is-num">مانده</span>
        <span>ماهیت</span>
      </div>
      {data.map((row, idx) => {
        const balance = row.balance || 0
        const isDebit = balance > 0.01
        const isCredit = balance < -0.01
        return (
          <div
            key={row.id || idx}
            className={`acct-strip${isClickable ? ' is-clickable' : ''}`}
            tabIndex={isClickable ? 0 : undefined}
            role={isClickable ? 'button' : undefined}
            onClick={() => isClickable && onRowClick(row)}
            onKeyDown={(event) => {
              if (isClickable && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault()
                onRowClick(row)
              }
            }}
          >
            <span className="acct-number col-code">{row.code}</span>
            <span style={{ fontWeight: 600 }}>{row.name}</span>
            <span className="acct-number col-code">{showFullCode ? (row.full_code || '—') : ''}</span>
            <span className={`acct-number${row.total_debit > 0 ? ' acct-debit' : ''}`}>{formatRial(row.total_debit || 0)}</span>
            <span className={`acct-number${row.total_credit > 0 ? ' acct-credit' : ''}`}>{formatRial(row.total_credit || 0)}</span>
            <span className={`acct-number${isDebit ? ' acct-debit' : isCredit ? ' acct-credit' : ''}`}>{formatRial(Math.abs(balance))}</span>
            <span>
              {isDebit ? (
                <span className="acct-balance-badge acct-balance-badge--debit">بد</span>
              ) : isCredit ? (
                <span className="acct-balance-badge acct-balance-badge--credit">بس</span>
              ) : (
                <span className="acct-balance-badge acct-balance-badge--balanced">—</span>
              )}
            </span>
          </div>
        )
      })}
      <LiveTBalance debit={totals.debit} credit={totals.credit} label="تراز آزمایشی لحظه‌ای" compact={compactView} />
    </div>
  )
}
