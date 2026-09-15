import { Button, Field, FilterBar } from './ui'
import { formatNumber } from '../utils/format'
import { fromLegacy } from '../styles/tw.js'

export const EMPTY_TRIAL_BALANCE_FILTER = {
  code: '',
  name: '',
}

export function applyTrialBalanceFilter(rows, filter) {
  if (!rows?.length) return []
  const code = (filter?.code || '').trim().toLowerCase()
  const name = (filter?.name || '').trim().toLowerCase()
  if (!code && !name) return rows
  return rows.filter((row) => {
    if (code && !String(row.account_code || '').toLowerCase().includes(code)) return false
    if (name && !String(row.account_name || '').toLowerCase().includes(name)) return false
    return true
  })
}

const TRIAL_AMOUNT_KEYS = [
  'opening_debit',
  'opening_credit',
  'turnover_debit',
  'turnover_credit',
  'balance_debit',
  'balance_credit',
]

export function sumTrialBalanceTotals(rows) {
  const totals = {}
  for (const key of TRIAL_AMOUNT_KEYS) {
    totals[key] = rows.reduce((sum, row) => sum + (Number(row[key]) || 0), 0)
  }
  const td = totals.turnover_debit || 0
  const tc = totals.turnover_credit || 0
  totals.raw_turnover_debit = td
  totals.raw_turnover_credit = tc
  totals.turnover_balanced = td === tc
  return totals
}

export function trialBalanceFilterActive(filter) {
  return Boolean((filter?.code || '').trim() || (filter?.name || '').trim())
}

export default function TrialBalanceFilterPanel({
  codeLabel,
  nameLabel,
  value,
  onChange,
  onReset,
  shownCount,
  totalCount,
}) {
  const filtered = shownCount != null && totalCount != null && shownCount !== totalCount

  return (
    <div className={fromLegacy("trial-balance-filter-panel")}>
      <FilterBar>
        <Field label={codeLabel}>
          <input
            className={fromLegacy("search-input")}
            value={value.code}
            onChange={(e) => onChange({ ...value, code: e.target.value })}
            placeholder="جستجوی زنده…"
          />
        </Field>
        <Field label={nameLabel}>
          <input
            className={fromLegacy("search-input")}
            value={value.name}
            onChange={(e) => onChange({ ...value, name: e.target.value })}
            placeholder="جستجوی زنده…"
          />
        </Field>
        <div className={fromLegacy("page-filters-actions")}>
          <Button type="button" variant="ghost" onClick={onReset}>
            پاک کردن فیلترها
          </Button>
        </div>
      </FilterBar>
      {filtered && (
        <p className={fromLegacy("record-filter-count muted")}>
          <strong>{formatNumber(shownCount)}</strong> از {formatNumber(totalCount)} حساب
        </p>
      )}
    </div>
  )
}
