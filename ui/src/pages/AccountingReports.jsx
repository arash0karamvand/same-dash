// صفحه گزارش‌های حسابداری (تراز کل، معین، تفصیلی)

import { useCallback, useEffect, useState } from 'react'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import { useTrialBalance } from '../accounting/useTrialBalance'
import ReportFilters from '../components/accounting/ReportFilters'
import TrialBalanceView from '../components/accounting/TrialBalanceView'
import TableViewToggle from '../components/accounting/TableViewToggle'
import {
  AccountingPageHeader,
  AccountingSummary,
  AccountingToolbar,
} from '../components/accounting/AccountingERP'
import { Button } from '../components/ui'
import { ACCOUNTING_MENU, TRIAL_BALANCE_LEVEL } from '../config/accountingTerms'
import Icon from '../components/icons/Icon'
import { formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

export default function AccountingReports({ tab = 'trial-balance' }) {
  const [accountOptions, setAccountOptions] = useState([])
  const [subsidiaryOptions, setSubsidiaryOptions] = useState([])

  const api = accountingApi
  const level = TRIAL_BALANCE_LEVEL[tab] || 'general'
  const fetchBalance = useCallback((params) => api.trialBalance(params), [api])
  const { state, setFilters, reset, reload } = useTrialBalance(level, fetchBalance, 'office')
  const { filters, rows: data, totals, loading, error } = state

  // بارگذاری لیست حساب‌ها برای فیلتر
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const accounts = resultList(await api.accounts())
        const opts = []
        for (const group of accounts || []) {
          for (const acc of group.accounts || []) {
            opts.push({
              value: String(acc.id),
              label: `${acc.code || acc.sort_order} — ${acc.name}`,
            })
          }
        }
        setAccountOptions(opts)
      } catch (err) {
        console.error('خطا در بارگذاری حساب‌ها:', err)
      }
    }
    const timeoutId = setTimeout(loadAccounts, 0)
    return () => clearTimeout(timeoutId)
  }, [api])

  // بارگذاری معین‌ها وقتی حساب کل انتخاب شد
  useEffect(() => {
    const loadSubsidiaries = async () => {
      if (!filters.accountId) {
        setSubsidiaryOptions([])
        return
      }
      try {
        const subs = resultList(await api.subsidiaries({ accountId: filters.accountId }))
        const opts = subs.map((s) => ({
              value: String(s.id),
              label: `${s.code} — ${s.name}`,
            }))
        setSubsidiaryOptions(opts)
      } catch (err) {
        console.error('خطا در بارگذاری معین‌ها:', err)
        setSubsidiaryOptions([])
      }
    }
    const timeoutId = setTimeout(loadSubsidiaries, 0)
    return () => clearTimeout(timeoutId)
  }, [api, filters.accountId])

  const handleReset = () => {
    reset()
  }

  const handleExport = () => {
    const rows = [
      ['کد', 'عنوان حساب', 'بدهکار', 'بستانکار', 'مانده'],
      ...data.map((row) => [
        row.full_code || row.code || '',
        row.name || '',
        row.total_debit || 0,
        row.total_credit || 0,
        Math.abs(row.balance || 0),
      ]),
    ]
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\n')}`
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    link.download = `${tab}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className={fromLegacy('accounting-reports-page')}>
      <AccountingPageHeader
        eyebrow="گزارش‌های مالی"
        title={ACCOUNTING_MENU[tab] || 'تراز حساب‌ها'}
        description="مانده و گردش حساب‌ها را در سطح انتخاب‌شده بررسی کنید."
        actions={<TableViewToggle showPrint />}
      />

      <ReportFilters
        filters={filters}
        onChange={setFilters}
        accountOptions={accountOptions}
        subsidiaryOptions={subsidiaryOptions}
        showSubsidiary={level !== 'general'}
        onReset={handleReset}
      />

      <AccountingToolbar>
        <Button variant="primary" onClick={reload} disabled={loading}>
          <Icon name="refresh-cw" size={16} />
          <span>به‌روزرسانی</span>
        </Button>
        <Button variant="secondary" onClick={handleExport}>
          <Icon name="download" size={16} />
          <span>خروجی CSV</span>
        </Button>
        <span className={fromLegacy("muted small")}>{data.length.toLocaleString('fa-IR')} ردیف</span>
      </AccountingToolbar>

      <AccountingSummary items={[
        { label: 'جمع بدهکار', value: formatRial(totals.debit) },
        { label: 'جمع بستانکار', value: formatRial(totals.credit) },
        {
          label: 'اختلاف تراز',
          value: formatRial(Math.abs(totals.debit - totals.credit)),
          tone: totals.debit === totals.credit ? 'success' : 'warning',
        },
      ]} />

      {error && (
        <div
          style={{
            padding: '1rem',
            background: 'var(--danger-soft)',
            color: 'var(--danger)',
            borderRadius: '0.5rem',
            marginBottom: '1rem',
          }}
        >
          {error}
        </div>
      )}

      <TrialBalanceView data={data} level={level} loading={loading} />
    </div>
  )
}
