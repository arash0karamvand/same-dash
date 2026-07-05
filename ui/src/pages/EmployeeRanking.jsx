// رده‌بندی کارکنان — فروش و حضور به تفکیک شعبه

import { useEffect, useState } from 'react'
import { salesApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar } from '../components/ui'
import { formatMoney } from '../utils/format'
import { currentJalali, isoToJalali, todayIso, toPersianDigits } from '../utils/jalali'

const PERIOD_OPTIONS = [
  { value: 'day', label: 'روز' },
  { value: 'month', label: 'ماه' },
  { value: 'year', label: 'سال' },
]

const BRANCHES = [
  { value: '', label: 'همه شعب' },
  { value: 'branch_1', label: 'کمرد' },
  { value: 'branch_2', label: 'پاسداران' },
]

function buildYearOptions(curYear) {
  return Array.from({ length: 12 }, (_, i) => {
    const y = curYear - i
    return { value: String(y), label: toPersianDigits(y) }
  })
}

function buildParams(period, dayIso, monthYear, monthValue, yearValue, branch, jNow) {
  const params = { period, branch: branch || undefined }
  if (period === 'year') {
    params.year = yearValue
  } else if (period === 'month') {
    params.year = monthYear
    params.month = monthValue
  } else {
    const j = isoToJalali(dayIso) || jNow
    params.year = j.year
    params.month = j.month
    params.day = j.day
  }
  return params
}

export default function EmployeeRanking() {
  const jNow = currentJalali()
  const [period, setPeriod] = useState('month')
  const [dayIso, setDayIso] = useState(todayIso())
  const [monthYear, setMonthYear] = useState(jNow.year)
  const [monthValue, setMonthValue] = useState(jNow.month)
  const [yearValue, setYearValue] = useState(jNow.year)
  const [branch, setBranch] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState({})

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const params = buildParams(period, dayIso, monthYear, monthValue, yearValue, branch, jNow)
      const result = await salesApi.employeeRanking(params)
      setData(result)
      if (result?.results?.length) {
        setExpanded({ [result.results[0].user_id]: true })
      } else {
        setExpanded({})
      }
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const rankColor = (rank) => {
    if (rank === 1) return '#f59e0b'
    if (rank === 2) return '#94a3b8'
    if (rank === 3) return '#b45309'
    return '#6366f1'
  }

  const toggleRow = (userId) => {
    setExpanded((prev) => ({ ...prev, [userId]: !prev[userId] }))
  }

  return (
    <div className="page employee-ranking-page">
      <Card title="رده‌بندی کارکنان">
        <p className="muted small" style={{ marginBottom: 16 }}>
          شعبه ثابت کارمند، شعب حضور در بازه، و فروش به تفکیک هر شعبه نمایش داده می‌شود.
        </p>
        <FilterBar>
          <Field label="بازه">
            <Select value={period} onChange={setPeriod} options={PERIOD_OPTIONS} />
          </Field>
          {period === 'day' && (
            <Field label="روز">
              <PersianDateInput value={dayIso} onChange={setDayIso} placeholder="انتخاب روز" />
            </Field>
          )}
          {period === 'month' && (
            <Field label="ماه">
              <PersianMonthPicker
                year={monthYear}
                month={monthValue}
                onChange={(y, m) => { setMonthYear(y); setMonthValue(m) }}
              />
            </Field>
          )}
          {period === 'year' && (
            <Field label="سال">
              <Select
                value={String(yearValue)}
                onChange={(v) => setYearValue(Number(v))}
                options={buildYearOptions(jNow.year)}
              />
            </Field>
          )}
          <Field label="فیلتر رتبه‌بندی">
            <Select value={branch} onChange={setBranch} options={BRANCHES} />
          </Field>
          <div className="page-filters-actions">
            <Button type="button" onClick={load} disabled={loading}>
              {loading ? 'در حال جستجو…' : 'جستجو'}
            </Button>
          </div>
        </FilterBar>

        {error && <div className="alert-error">{error}</div>}
        {!loading && !error && !data?.results?.length && (
          <EmptyState message="داده‌ای برای این بازه نیست. (برای تست: python manage.py seed_ranking_demo)" />
        )}
        {data?.results?.length > 0 && (
          <>
            <p className="muted small">مجموع: {formatMoney(data.total_final || 0)}</p>
            <div className="ranking-list">
              {data.results.map((row) => (
                <div key={row.user_id} className="ranking-card">
                  <button type="button" className="ranking-card-head" onClick={() => toggleRow(row.user_id)}>
                    <Badge color={rankColor(row.rank)}>{toPersianDigits(row.rank)}</Badge>
                    <div className="ranking-card-main">
                      <strong>{row.full_name}</strong>
                      <span className="muted small">
                        شعبه ثابت: {row.home_branch_label || '—'}
                      </span>
                    </div>
                    <div className="ranking-card-total">
                      <span className="muted small">فروش</span>
                      <strong>{formatMoney(row.total_final)}</strong>
                      <span className="muted small">{toPersianDigits(row.sale_count)} فقره</span>
                    </div>
                    <span className="ranking-expand">{expanded[row.user_id] ? '▲' : '▼'}</span>
                  </button>

                  {expanded[row.user_id] && (
                    <div className="ranking-card-body">
                      <div className="ranking-section">
                        <h4>حضور در بازه</h4>
                        {row.attendance_branches?.length ? (
                          <ul className="ranking-branch-list">
                            {row.attendance_branches.map((item) => (
                              <li key={`att-${item.branch}`}>
                                <span>{item.branch_label}</span>
                                <span>{toPersianDigits(item.days)} روز حضور</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted small">حضور ثبت‌شده‌ای در این بازه نیست.</p>
                        )}
                      </div>
                      <div className="ranking-section">
                        <h4>فروش به تفکیک شعبه</h4>
                        {row.sales_by_branch?.length ? (
                          <ul className="ranking-branch-list">
                            {row.sales_by_branch.map((item) => (
                              <li key={`sale-${item.branch}`}>
                                <span>{item.branch_label}</span>
                                <span>
                                  {formatMoney(item.total_final)}
                                  {' '}
                                  <span className="muted">({toPersianDigits(item.sale_count)} فقره)</span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted small">فروشی ثبت نشده.</p>
                        )}
                        {row.sales_by_branch?.length > 1 && (
                          <p className="muted small ranking-all-total">
                            جمع همه شعب: {formatMoney(row.total_all_branches)} ({toPersianDigits(row.sale_count_all_branches)} فقره)
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
