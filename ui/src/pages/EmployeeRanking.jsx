// رده‌بندی کارکنان — فروش، تخفیف، دریافت قبل از تحویل

import { useEffect, useState } from 'react'
import { configApi, salesApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { formatMoney, formatNumber } from '../utils/format'
import { currentJalali, isoToJalali, todayIso, toPersianDigits } from '../utils/jalali'
import { isSystemAdmin } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const PERIOD_OPTIONS = [
  { value: 'day', label: 'روز' },
  { value: 'month', label: 'ماه' },
  { value: 'year', label: 'سال' },
]

const EMPTY_WEIGHTS = { sales: 100, pre_delivery: 0, discount_percent: 0, discount_rial: 0 }

const WEIGHT_FIELDS = [
  { key: 'sales', label: 'فروش', hint: 'فروش بیشتر رتبه را بالا می‌برد.' },
  { key: 'pre_delivery', label: 'دریافت قبل از تحویل', hint: 'پول بیشتر قبل از تحویل رتبه را بالا می‌برد.' },
  { key: 'discount_percent', label: 'میانگین درصد تخفیف', hint: 'تخفیف درصدی بیشتر رتبه را پایین می‌آورد.' },
  { key: 'discount_rial', label: 'جمع تخفیف ریالی', hint: 'جمع تخفیف بیشتر رتبه را پایین می‌آورد.' },
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

function clampWeight(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.min(100, Math.max(0, Math.round(n)))
}

function formatPercent(value) {
  const n = Number(value || 0)
  return `${n.toLocaleString('fa-IR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}٪`
}

export default function EmployeeRanking() {
  useRegisterPageGuide('ranking', PAGE_GUIDE_DEFAULTS.ranking)
  const { user } = useAuth()
  const { branchOptions, rankingSettings, refresh: refreshConfig } = useConfig()
  const canEditWeights = isSystemAdmin(user)
  const branchFilterOptions = [{ value: '', label: 'همه شعب' }, ...branchOptions]
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
  const [info, setInfo] = useState('')
  const [expanded, setExpanded] = useState({})
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [weights, setWeights] = useState({ ...EMPTY_WEIGHTS, ...rankingSettings })
  const [savingWeights, setSavingWeights] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const params = buildParams(period, dayIso, monthYear, monthValue, yearValue, branch, jNow)
      const result = await salesApi.employeeRanking(params)
      setData(result)
      if (result?.weights) {
        setWeights({ ...EMPTY_WEIGHTS, ...result.weights })
      }
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

  useEffect(() => {
    if (rankingSettings) {
      setWeights((prev) => ({ ...EMPTY_WEIGHTS, ...prev, ...rankingSettings }))
    }
  }, [rankingSettings])

  const rankColor = (rank) => {
    if (rank === 1) return 'var(--warning)'
    if (rank === 2) return '#94a3b8'
    if (rank === 3) return '#b45309'
    return 'var(--accent)'
  }

  const toggleRow = (userId) => {
    setExpanded((prev) => ({ ...prev, [userId]: !prev[userId] }))
  }

  const saveWeights = async () => {
    setSavingWeights(true)
    setError('')
    setInfo('')
    try {
      const saved = await configApi.saveRankingSettings({
        sales: clampWeight(weights.sales),
        pre_delivery: clampWeight(weights.pre_delivery),
        discount_percent: clampWeight(weights.discount_percent),
        discount_rial: clampWeight(weights.discount_rial),
      })
      setWeights({ ...EMPTY_WEIGHTS, ...saved })
      setInfo('وزن‌های رتبه ذخیره شد.')
      await refreshConfig()
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSavingWeights(false)
    }
  }

  return (
    <div className={fromLegacy("page employee-ranking-page")}>
      <Card title="رده‌بندی کارکنان">
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
            <Select value={branch} onChange={setBranch} options={branchFilterOptions} />
          </Field>
          <div className={fromLegacy("page-filters-actions")}>
            <Button type="button" onClick={load} disabled={loading}>
              {loading ? 'در حال جستجو…' : 'جستجو'}
            </Button>
          </div>
        </FilterBar>

        <div className={fromLegacy("ranking-settings")}>
          <button
            type="button"
            className={fromLegacy("ranking-settings-toggle")}
            onClick={() => setSettingsOpen((open) => !open)}
          >
            تنظیمات رتبه {settingsOpen ? '▲' : '▼'}
          </button>
          {settingsOpen && (
            <div className={fromLegacy("ranking-settings-body")}>
              <p className={fromLegacy("muted small")}>
                وزن هر شاخص بین ۰ تا ۱۰۰ است. صفر یعنی فقط نمایش، بدون اثر روی رتبه.
                تخفیف بیشتر رتبه را پایین و فروش یا دریافت قبل از تحویل رتبه را بالا می‌برد.
              </p>
              <div className={fromLegacy("ranking-weights-grid")}>
                {WEIGHT_FIELDS.map((field) => (
                  <Field key={field.key} label={field.label}>
                    <input
                      className={fromLegacy("ltr")}
                      type="number"
                      min="0"
                      max="100"
                      value={weights[field.key]}
                      disabled={!canEditWeights}
                      onChange={(e) => setWeights((prev) => ({
                        ...prev,
                        [field.key]: e.target.value,
                      }))}
                    />
                    <span className={fromLegacy("muted small")}>{field.hint}</span>
                  </Field>
                ))}
              </div>
              {canEditWeights ? (
                <Button type="button" onClick={saveWeights} disabled={savingWeights}>
                  {savingWeights ? 'در حال ذخیره…' : 'ذخیره وزن‌ها'}
                </Button>
              ) : (
                <p className={fromLegacy("muted small")}>فقط مدیر سیستم می‌تواند وزن‌ها را تغییر دهد.</p>
              )}
            </div>
          )}
        </div>

        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        {info && <div className={fromLegacy("alert-info")}>{info}</div>}
        {!loading && !error && !data?.results?.length && (
          <EmptyState message="داده‌ای برای این بازه نیست. (برای تست: python manage.py seed_ranking_demo)" />
        )}
        {data?.results?.length > 0 && (
          <>
            <p className={fromLegacy("muted small")}>
              مجموع فروش: {formatMoney(data.total_final || 0)}
              {' · '}
              جمع تخفیف: {formatMoney(data.total_discount || 0)}
              {' · '}
              قبل از تحویل: {formatMoney(data.total_pre_delivery || 0)}
            </p>
            <div className={fromLegacy("ranking-list")}>
              {data.results.map((row) => (
                <div key={row.user_id} className={fromLegacy("ranking-card")}>
                  <button type="button" className={fromLegacy("ranking-card-head")} onClick={() => toggleRow(row.user_id)}>
                    <Badge color={rankColor(row.rank)}>{toPersianDigits(row.rank)}</Badge>
                    <div className={fromLegacy("ranking-card-main")}>
                      <strong>{row.full_name}</strong>
                      <span className={fromLegacy("muted small")}>
                        شعبه ثابت: {row.home_branch_label || '—'}
                      </span>
                    </div>
                    <div className={fromLegacy("ranking-card-total")}>
                      <span className={fromLegacy("muted small")}>فروش</span>
                      <strong>{formatMoney(row.total_final)}</strong>
                      <span className={fromLegacy("muted small")}>{toPersianDigits(row.sale_count)} فقره</span>
                    </div>
                    <span className={fromLegacy("ranking-expand")}>{expanded[row.user_id] ? '▲' : '▼'}</span>
                  </button>
                  <div className={fromLegacy("ranking-metrics")}>
                    <span>میانگین تخفیف: <strong>{formatPercent(row.avg_discount_percent)}</strong></span>
                    <span>جمع تخفیف: <strong>{formatMoney(row.total_discount)}</strong></span>
                    <span>قبل از تحویل: <strong>{formatMoney(row.pre_delivery_paid)}</strong></span>
                  </div>

                  {expanded[row.user_id] && (
                    <div className={fromLegacy("ranking-card-body")}>
                      <div className={fromLegacy("ranking-section")}>
                        <h4>حضور در بازه</h4>
                        {row.attendance_branches?.length ? (
                          <ul className={fromLegacy("ranking-branch-list")}>
                            {row.attendance_branches.map((item) => (
                              <li key={`att-${item.branch}`}>
                                <span>{item.branch_label}</span>
                                <span>{toPersianDigits(item.days)} روز حضور</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={fromLegacy("muted small")}>حضور ثبت‌شده‌ای در این بازه نیست.</p>
                        )}
                      </div>
                      <div className={fromLegacy("ranking-section")}>
                        <h4>فروش به تفکیک شعبه</h4>
                        {row.sales_by_branch?.length ? (
                          <ul className={fromLegacy("ranking-branch-list")}>
                            {row.sales_by_branch.map((item) => (
                              <li key={`sale-${item.branch}`}>
                                <span>{item.branch_label}</span>
                                <span>
                                  {formatMoney(item.total_final)}
                                  {' '}
                                  <span className={fromLegacy("muted")}>({toPersianDigits(item.sale_count)} فقره)</span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className={fromLegacy("muted small")}>فروشی ثبت نشده.</p>
                        )}
                        {row.sales_by_branch?.length > 1 && (
                          <p className={fromLegacy("muted small ranking-all-total")}>
                            جمع همه شعب: {formatMoney(row.total_all_branches)} ({toPersianDigits(row.sale_count_all_branches)} فقره)
                          </p>
                        )}
                      </div>
                      <div className={fromLegacy("ranking-section")}>
                        <h4>نمره رتبه</h4>
                        <p className={fromLegacy("muted small")}>
                          نمره: {formatNumber(row.score || 0)}
                          {' — '}
                          وزن فروش {toPersianDigits(data.weights?.sales ?? 0)}،
                          قبل از تحویل {toPersianDigits(data.weights?.pre_delivery ?? 0)}،
                          درصد تخفیف {toPersianDigits(data.weights?.discount_percent ?? 0)}،
                          تخفیف ریالی {toPersianDigits(data.weights?.discount_rial ?? 0)}
                        </p>
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
