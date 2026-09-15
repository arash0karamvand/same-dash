// پنل جمع‌بندی فروش شخصی — روز / ماه / سال شمسی

import { useEffect, useState } from 'react'
import PersianDateInput from './PersianDateInput'
import PersianMonthPicker from './PersianMonthPicker'
import Select from './Select'
import { Button, Card, Field } from './ui'
import { salesApi } from '../api/client'
import { formatMoney } from '../utils/format'
import { currentJalali, formatJalali, jalaliToIso, PERSIAN_MONTHS, todayIso, toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const PERIOD_OPTIONS = [
  { value: 'day', label: 'روز' },
  { value: 'month', label: 'ماه' },
  { value: 'year', label: 'سال' },
]

function buildYearOptions(curYear) {
  return Array.from({ length: 12 }, (_, i) => {
    const y = curYear - i
    return { value: String(y), label: toPersianDigits(y) }
  })
}

export default function PersonalSalesPanel({
  collapsed,
  onToggleCollapse,
  onApplyListFilter,
  monthOnly = false,
}) {
  const jNow = currentJalali()
  const [period, setPeriod] = useState(monthOnly ? 'month' : 'day')
  const [dayIso, setDayIso] = useState(todayIso())
  const [monthYear, setMonthYear] = useState(jNow.year)
  const [monthValue, setMonthValue] = useState(jNow.month)
  const [yearValue, setYearValue] = useState(jNow.year)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadStats = async () => {
    setLoading(true)
    setError('')
    try {
      let data
      if (period === 'day') {
        data = await salesApi.dailyReport(dayIso)
      } else if (period === 'month') {
        data = await salesApi.monthlyReport(monthYear, monthValue)
      } else {
        data = await salesApi.yearlyReport(yearValue)
      }
      setStats(data)
    } catch (e) {
      setError(e.message)
      setStats(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!collapsed) loadStats()
  }, [collapsed, period, dayIso, monthYear, monthValue, yearValue])

  const periodLabel = () => {
    if (period === 'day') {
      const j = currentJalali()
      if (stats?.jalali_year) {
        return formatJalali(jalaliToIso(stats.jalali_year, stats.jalali_month, stats.jalali_day))
      }
      return formatJalali(dayIso)
    }
    if (period === 'month') {
      return `${PERSIAN_MONTHS[(stats?.jalali_month || monthValue) - 1]} ${toPersianDigits(stats?.jalali_year || monthYear)}`
    }
    return `سال ${toPersianDigits(stats?.jalali_year || yearValue)}`
  }

  const applyToList = () => {
    if (period === 'day') {
      onApplyListFilter?.({ date_from: dayIso, date_to: dayIso })
      return
    }
    if (period === 'month') {
      const start = jalaliToIso(monthYear, monthValue, 1)
      const endDay = monthValue <= 6 ? 31 : monthValue <= 11 ? 30 : 29
      onApplyListFilter?.({ date_from: start, date_to: jalaliToIso(monthYear, monthValue, endDay) })
      return
    }
    const start = jalaliToIso(yearValue, 1, 1)
    onApplyListFilter?.({ date_from: start, date_to: jalaliToIso(yearValue, 12, 29) })
  }

  return (
    <Card
      className={fromLegacy(`personal-sales-panel ${collapsed ? 'is-collapsed' : ''}`)}
      title={monthOnly ? 'فروش ماهانه من' : 'فروش من'}
      actions={
        <button type="button" className={fromLegacy("link collapse-toggle")} onClick={onToggleCollapse}>
          {collapsed ? 'نمایش ▼' : 'بستن ▲'}
        </button>
      }
    >
      {!collapsed && (
        <>
          <div className={fromLegacy("personal-sales-filters")}>
            {!monthOnly && (
            <Field label="بازه">
              <Select
                value={period}
                onChange={setPeriod}
                options={PERIOD_OPTIONS}
              />
            </Field>
            )}
            {period === 'day' && (
              <Field label="روز">
                <PersianDateInput
                  value={dayIso}
                  onChange={setDayIso}
                  placeholder="انتخاب روز"
                />
              </Field>
            )}
            {period === 'month' && (
              <Field label="ماه">
                <PersianMonthPicker
                  year={monthYear}
                  month={monthValue}
                  onChange={(y, m) => { setMonthYear(y); setMonthValue(m) }}
                  onClear={() => { setMonthYear(jNow.year); setMonthValue(jNow.month) }}
                />
              </Field>
            )}
            {period === 'year' && !monthOnly && (
              <Field label="سال">
                <Select
                  value={String(yearValue)}
                  onChange={(v) => setYearValue(Number(v))}
                  options={buildYearOptions(jNow.year)}
                />
              </Field>
            )}
            <div className={fromLegacy("page-filters-actions")}>
              <Button type="button" onClick={loadStats} disabled={loading}>
                {loading ? '…' : 'بروزرسانی'}
              </Button>
              {!monthOnly && onApplyListFilter && (
              <Button type="button" variant="ghost" onClick={applyToList}>
                اعمال روی لیست
              </Button>
              )}
            </div>
          </div>
          {error && <div className={fromLegacy("alert-error")}>{error}</div>}
          <div className={fromLegacy("personal-sales-stats")}>
            <div>
              <span className={fromLegacy("muted")}>بازه</span>
              <strong>{periodLabel()}</strong>
            </div>
            <div>
              <span className={fromLegacy("muted")}>مبلغ</span>
              <strong className={fromLegacy("stat-value")}>{formatMoney(stats?.total_final || 0)}</strong>
            </div>
            <div>
              <span className={fromLegacy("muted")}>تعداد</span>
              <strong>{stats?.count || 0} فقره</strong>
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
