// صفحه مراکز درآمد (سود و زیان شعب)

import { useState, useEffect, useCallback } from 'react'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import ProfitCenterReport from '../components/accounting/ProfitCenterReport'
import { AccountingDataPanel, AccountingPageHeader, AccountingSummary } from '../components/accounting/AccountingERP'
import { Field, Button } from '../components/ui'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import Icon from '../components/icons/Icon'
import { formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

export default function AccountingProfitCenters() {
  const [data, setData] = useState([])
  const [branches, setBranches] = useState([])
  const [filters, setFilters] = useState({
    branchId: '',
    dateFrom: '',
    dateTo: '',
  })
  const [loading, setLoading] = useState(false)

  const loadBranches = useCallback(async () => {
    try {
      const result = await accountingApi.profitCenters()
      setBranches(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری شعب:', err)
      setBranches([])
    }
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.profitCenters(filters)
      const rows = resultList(result)
      setData(filters.branchId ? rows.filter((row) => String(row.branch || row.branch_id) === filters.branchId) : rows)
    } catch (err) {
      console.error('خطا در بارگذاری داده‌ها:', err)
      setData([])
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    const timeoutId = setTimeout(loadBranches, 0)
    return () => clearTimeout(timeoutId)
  }, [loadBranches])

  useEffect(() => {
    const timeoutId = setTimeout(loadData, 0)
    return () => clearTimeout(timeoutId)
  }, [loadData])

  const totalRevenue = Array.isArray(data) ? data.reduce((sum, item) => sum + (item.revenue || 0), 0) : 0
  const totalExpense = Array.isArray(data) ? data.reduce((sum, item) => sum + (item.expense || 0), 0) : 0
  const totalProfit = totalRevenue - totalExpense

  return (
    <div className={fromLegacy('accounting-profit-centers-page')}>
      <AccountingPageHeader
        eyebrow="تحلیل عملکرد"
        title="مراکز درآمد"
        description="مقایسه درآمد، هزینه و سود خالص شعب و واحدهای فروش"
      />

      <AccountingDataPanel title="فیلتر گزارش">
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <Field label="شعبه">
            <Select
              value={filters.branchId}
              onChange={(e) => setFilters({ ...filters, branchId: e.target.value })}
              options={[
                { value: '', label: 'همه شعب' },
                ...(Array.isArray(branches) ? branches : []).map((b) => ({
                  value: String(b.branch || b.branch_id || b.id),
                  label: b.label || b.branch_name || b.name,
                })),
              ]}
            />
          </Field>

          <Field label="از تاریخ">
            <PersianDateInput
              value={filters.dateFrom}
              onChange={(val) => setFilters({ ...filters, dateFrom: val })}
            />
          </Field>

          <Field label="تا تاریخ">
            <PersianDateInput
              value={filters.dateTo}
              onChange={(val) => setFilters({ ...filters, dateTo: val })}
            />
          </Field>

          <Button variant="primary" onClick={loadData} disabled={loading}>
            <Icon name="search" size={16} />
            <span>جستجو</span>
          </Button>
        </div>
      </AccountingDataPanel>

      <AccountingSummary items={[
        { label: 'مجموع درآمد', value: formatRial(totalRevenue), tone: 'success' },
        { label: 'مجموع هزینه', value: formatRial(totalExpense), tone: 'danger' },
        { label: 'سود خالص', value: formatRial(totalProfit), tone: totalProfit >= 0 ? 'success' : 'danger' },
        { label: 'تعداد مراکز', value: data.length.toLocaleString('fa-IR') },
      ]} />

      <ProfitCenterReport data={data} loading={loading} />
    </div>
  )
}
