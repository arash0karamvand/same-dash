// صفحه تحلیل RFM در پورتال اداری: داشبورد، لیست کار، تنظیمات امتیاز و اکشن.

import { useCallback, useEffect, useState } from 'react'
import { rfmApi } from '../api/client'
import Select from '../components/Select'
import MoneyInput from '../components/MoneyInput'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { PAGE_SIZE } from '../config/pagination'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { hasPermission } from '../utils/permissions'
import { formatDate, formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const TABS = [
  { id: 'dashboard', label: 'داشبورد' },
  { id: 'worklist', label: 'لیست کار' },
  { id: 'settings', label: 'تنظیمات' },
]

const ACTION_OPTIONS = [
  { value: 'playbook', label: 'نمایش راهنما' },
  { value: 'call', label: 'تماس فروش' },
  { value: 'sms', label: 'پیامک' },
  { value: 'vip', label: 'دعوت VIP' },
]

const SCORE_VALUES = [5, 4, 3, 2, 1]

const EMPTY_SEGMENT = {
  name: '',
  color: '#6366f1',
  sort_order: 0,
  is_active: true,
  description: '',
  r_scores: [5],
  f_scores: [5],
  m_scores: [5],
  action_type: 'playbook',
  action_title: '',
  action_body: '',
  no_discount: false,
  auto_sms: false,
  sms_template: '{name} عزیز، {shop_name} منتظر دیدار شماست.',
  sms_cooldown_days: 90,
}

function toggleScore(list, score) {
  const next = list.includes(score) ? list.filter((item) => item !== score) : [...list, score]
  return next.sort((a, b) => b - a)
}

function ScoreChecks({ label, values, onChange }) {
  return (
    <Field label={label}>
      <div className="rfm-score-row">
        {SCORE_VALUES.map((score) => (
          <label key={score} className="rfm-score-chip">
            <input
              type="checkbox"
              checked={values.includes(score)}
              onChange={() => onChange(toggleScore(values, score))}
            />
            {toPersianDigits(score)}
          </label>
        ))}
      </div>
    </Field>
  )
}

function ThresholdEditor({ title, rows, kind, onChange }) {
  const key = kind === 'r' ? 'max_days' : kind === 'f' ? 'min_count' : 'min_amount'
  const label = kind === 'r' ? 'حداکثر روز' : kind === 'f' ? 'حداقل تعداد فاکتور' : 'حداقل مبلغ'
  return (
    <Card title={title}>
      <div className="rfm-threshold-grid">
        <span className={fromLegacy('muted')}>امتیاز</span>
        <span className={fromLegacy('muted')}>{label}</span>
        {(rows || []).map((row, index) => (
          <FragmentRow
            key={`${kind}-${index}`}
            score={row.score}
            kind={kind}
            value={row[key]}
            onChange={(value) => {
              const next = rows.map((item, i) => (i === index ? { ...item, [key]: value } : item))
              onChange(next)
            }}
          />
        ))}
      </div>
    </Card>
  )
}

function FragmentRow({ score, kind, value, onChange }) {
  return (
    <>
      <span>{toPersianDigits(score)}</span>
      {kind === 'm' ? (
        <MoneyInput value={value} onChange={(e) => onChange(Number(e.target.value || 0))} />
      ) : (
        <input
          className={fromLegacy('ltr')}
          type="number"
          min="0"
          value={value}
          onChange={(e) => onChange(Number(e.target.value || 0))}
        />
      )}
    </>
  )
}

export default function Rfm() {
  useRegisterPageGuide('rfm', PAGE_GUIDE_DEFAULTS.rfm)
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasPermission(user, 'manage_rfm')
  const canSend = hasPermission(user, 'send_sms')

  const [tab, setTab] = useState('dashboard')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [summary, setSummary] = useState(null)
  const [settings, setSettings] = useState(null)
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [recalculating, setRecalculating] = useState(false)

  const [customers, setCustomers] = useState([])
  const [customerTotal, setCustomerTotal] = useState(0)
  const [customerOffset, setCustomerOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [search, setSearch] = useState('')
  const [segmentFilter, setSegmentFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_SEGMENT)

  const loadSummary = useCallback(async () => {
    const data = await rfmApi.summary()
    setSummary(data)
    setSettings(data.settings)
    setSegments(data.segments || [])
  }, [])

  const loadCustomers = useCallback(async ({ append = false, offset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    const data = await rfmApi.customers({
      search: search.trim(),
      segmentId: segmentFilter || undefined,
      actionType: actionFilter || undefined,
      offset,
      limit: PAGE_SIZE,
    })
    setCustomers((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))
    setCustomerTotal(data.total || 0)
    setCustomerOffset(data.offset ?? offset)
  }, [search, segmentFilter, actionFilter])

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      await loadSummary()
      await loadCustomers()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [loadSummary, loadCustomers])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        await loadSummary()
        if (!cancelled) setError('')
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [loadSummary])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await loadCustomers()
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoadingMore(false)
      }
    })()
    return () => { cancelled = true }
  }, [loadCustomers])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY_SEGMENT, sort_order: segments.length })
    setModalOpen(true)
  }

  const openEdit = (segment) => {
    setEditing(segment)
    setForm({
      name: segment.name,
      color: segment.color || '#6366f1',
      sort_order: segment.sort_order || 0,
      is_active: segment.is_active,
      description: segment.description || '',
      r_scores: segment.r_scores || [],
      f_scores: segment.f_scores || [],
      m_scores: segment.m_scores || [],
      action_type: segment.action_type || 'playbook',
      action_title: segment.action_title || '',
      action_body: segment.action_body || '',
      no_discount: Boolean(segment.no_discount),
      auto_sms: Boolean(segment.auto_sms),
      sms_template: segment.sms_template || '',
      sms_cooldown_days: segment.sms_cooldown_days || 90,
    })
    setModalOpen(true)
  }

  const saveSettings = async (e) => {
    e.preventDefault()
    if (!canManage || !settings) return
    setSaving(true)
    try {
      const data = await rfmApi.updateSettings(settings)
      setSettings(data)
      setInfo('تنظیمات امتیاز ذخیره شد. برای اعمال روی مشتریان «محاسبه مجدد» را بزنید.')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const saveSegment = async (e) => {
    e.preventDefault()
    try {
      if (editing) await rfmApi.updateSegment(editing.id, form)
      else await rfmApi.createSegment(form)
      setModalOpen(false)
      await loadSummary()
      setInfo('بخش ذخیره شد.')
    } catch (err) {
      setError(err.message)
    }
  }

  const removeSegment = async (segment) => {
    if (!await confirm({
      title: 'حذف بخش',
      message: `حذف بخش «${segment.name}»؟ مشتریان این بخش به «سایر» می‌روند تا محاسبه بعدی.`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    await rfmApi.removeSegment(segment.id)
    await loadSummary()
  }

  const recalculate = async () => {
    if (!canManage) return
    if (!await confirm({
      title: 'محاسبه مجدد RFM',
      message: 'امتیاز همه مشتریان از روی فاکتورهای شمارش‌پذیر محاسبه می‌شود. پیامک خودکار فقط برای بخش‌هایی که فعال کرده‌اید ارسال می‌گردد.',
      confirmText: 'محاسبه شود',
    })) return
    setRecalculating(true)
    try {
      const result = await rfmApi.recalculate({ send_sms: true })
      await loadAll()
      setInfo(
        `محاسبه انجام شد: ${toPersianDigits(result.scored || 0)} مشتری، `
        + `${toPersianDigits(result.unmatched || 0)} بدون بخش، `
        + `${toPersianDigits(result.sms_sent || 0)} پیامک.`,
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setRecalculating(false)
    }
  }

  const sendSms = async (row) => {
    if (!await confirm({
      title: 'ارسال پیامک',
      message: `پیامک اکشن «${row.segment_name}» برای ${row.full_name} ارسال شود؟`,
      confirmText: 'ارسال',
    })) return
    try {
      const result = await rfmApi.sendSms(row.customer_id, { force: true })
      if (result.skipped) setInfo('این مشتری در دورهٔ انتظار پیامک است.')
      else setInfo(`پیامک برای ${row.full_name} ثبت شد.`)
    } catch (err) {
      setError(err.message)
    }
  }

  const openSegmentList = (segmentId) => {
    setSegmentFilter(segmentId == null ? 'other' : String(segmentId))
    setTab('worklist')
  }

  const segmentOptions = [
    { value: '', label: 'همه بخش‌ها' },
    { value: 'other', label: 'سایر' },
    ...segments.map((item) => ({ value: String(item.id), label: item.name })),
  ]

  return (
    <div className={fromLegacy('page')}>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-info')}>{info}</div>}

      <div className={fromLegacy('branch-tabs settings-tabs')}>
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={fromLegacy(`branch-tab ${tab === item.id ? 'active' : ''}`)}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className={fromLegacy('loading')}>در حال بارگذاری…</div>
      ) : (
        <>
          {tab === 'dashboard' && (
            <Card
              title="بخش‌بندی RFM"
              actions={canManage ? (
                <Button onClick={recalculate} disabled={recalculating}>
                  {recalculating ? 'در حال محاسبه…' : 'محاسبه مجدد'}
                </Button>
              ) : null}
            >
              <p className={fromLegacy('muted')}>
                آخرین محاسبه:{' '}
                {settings?.last_run_at ? formatDate(settings.last_run_at) : 'هنوز اجرا نشده است'}
                {settings?.score_method === 'threshold' ? ' — امتیازدهی با آستانهٔ دستی' : ' — امتیازدهی پنجک'}
              </p>
              <div className={fromLegacy('stat-grid')} style={{ marginTop: 12 }}>
                <StatCard label="مشتریان امتیازدهی‌شده" value={toPersianDigits(summary?.total || 0)} />
                <button type="button" className="rfm-segment-card" onClick={() => openSegmentList(null)}>
                  <StatCard
                    label="بدون بخش"
                    value={toPersianDigits(summary?.unmatched || 0)}
                    hint="برای دیدن لیست کلیک کنید"
                    accent="#94a3b8"
                  />
                </button>
              </div>
              <div className="rfm-segment-grid">
                {(summary?.segments || []).map((segment) => (
                  <button
                    key={segment.id}
                    type="button"
                    className="rfm-segment-card"
                    onClick={() => openSegmentList(segment.id)}
                  >
                    <StatCard
                      label={segment.name}
                      value={toPersianDigits(segment.customer_count || 0)}
                      hint={segment.action_title || ACTION_OPTIONS.find((o) => o.value === segment.action_type)?.label}
                      accent={segment.color}
                    />
                  </button>
                ))}
              </div>
            </Card>
          )}

          {tab === 'worklist' && (
            <Card title="لیست کار و مشتریان">
              <FilterBar>
                <Field label="جستجو">
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="نام یا موبایل"
                  />
                </Field>
                <Field label="بخش">
                  <Select
                    value={segmentFilter}
                    onChange={setSegmentFilter}
                    options={segmentOptions}
                    label="بخش"
                  />
                </Field>
                <Field label="اکشن">
                  <Select
                    value={actionFilter}
                    onChange={setActionFilter}
                    options={[{ value: '', label: 'همه اکشن‌ها' }, ...ACTION_OPTIONS]}
                    label="اکشن"
                  />
                </Field>
              </FilterBar>

              {customers.length === 0 ? (
                <EmptyState text="مشتری امتیازدهی‌شده‌ای یافت نشد. ابتدا محاسبه مجدد را اجرا کنید." />
              ) : (
                <>
                  <div className={fromLegacy('table-wrap rfm-table-desktop')}>
                    <table className={fromLegacy('table')}>
                      <thead>
                        <tr>
                          <th>مشتری</th>
                          <th>RFM</th>
                          <th>تازگی (روز)</th>
                          <th>تعداد فاکتور</th>
                          <th>مبلغ</th>
                          <th>بخش</th>
                          <th>اکشن</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {customers.map((row) => (
                          <tr key={row.id}>
                            <td>
                              <div>{row.full_name}</div>
                              <div className={fromLegacy('muted ltr')}>{row.phone}</div>
                            </td>
                            <td className="rfm-code ltr">{toPersianDigits(row.rfm_code)}</td>
                            <td>{toPersianDigits(row.r_raw)}</td>
                            <td>{toPersianDigits(row.f_raw)}</td>
                            <td>{formatMoney(row.m_raw)}</td>
                            <td><Badge color={row.segment_color}>{row.segment_name}</Badge></td>
                            <td>
                              <div>{row.action_title || '—'}</div>
                              {row.no_discount && <span className={fromLegacy('muted')}>بدون تخفیف</span>}
                            </td>
                            <td className={fromLegacy('row-actions')}>
                              {canSend && (row.action_type === 'sms' || row.sms_template) && (
                                <button type="button" className={fromLegacy('link')} onClick={() => sendSms(row)}>
                                  پیامک
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="rfm-cards-mobile">
                    {customers.map((row) => (
                      <div key={row.id} className={fromLegacy('m-card')}>
                        <div className={fromLegacy('m-card-head')}>
                          <strong>{row.full_name}</strong>
                          <Badge color={row.segment_color}>{row.segment_name}</Badge>
                        </div>
                        <div className={fromLegacy('m-card-grid')}>
                          <div><span className={fromLegacy('muted')}>RFM</span><span className="ltr">{toPersianDigits(row.rfm_code)}</span></div>
                          <div><span className={fromLegacy('muted')}>تازگی</span>{toPersianDigits(row.r_raw)} روز</div>
                          <div><span className={fromLegacy('muted')}>تکرار</span>{toPersianDigits(row.f_raw)}</div>
                          <div><span className={fromLegacy('muted')}>مبلغ</span>{formatMoney(row.m_raw)}</div>
                          <div><span className={fromLegacy('muted')}>اکشن</span>{row.action_title || '—'}</div>
                          <div><span className={fromLegacy('muted')}>موبایل</span><span className="ltr">{row.phone}</span></div>
                        </div>
                        {canSend && (row.action_type === 'sms' || row.sms_template) && (
                          <div className={fromLegacy('m-card-actions')}>
                            <button type="button" className={fromLegacy('link')} onClick={() => sendSms(row)}>ارسال پیامک</button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <LoadMoreButton
                    hasMore={customers.length < customerTotal}
                    loading={loadingMore}
                    pageSize={PAGE_SIZE}
                    onClick={() => loadCustomers({ append: true, offset: customerOffset + PAGE_SIZE })}
                  />
                </>
              )}
            </Card>
          )}

          {tab === 'settings' && (
            <>
              <Card title="اساس امتیازدهی">
                {!canManage && <p className={fromLegacy('muted')}>فقط مشاهده — برای ویرایش به مجوز مدیریت RFM نیاز است.</p>}
                {settings && (
                  <form onSubmit={saveSettings} className={fromLegacy('form')}>
                    <Field label="روش امتیاز">
                      <Select
                        value={settings.score_method}
                        onChange={(value) => setSettings({ ...settings, score_method: value })}
                        options={[
                          { value: 'quantile', label: 'پنجک (تقسیم مشتریان به ۵ گروه)' },
                          { value: 'threshold', label: 'آستانهٔ دستی (روز / تعداد / مبلغ)' },
                        ]}
                        disabled={!canManage}
                        label="روش امتیاز"
                      />
                    </Field>
                    <Field label="بازهٔ تحلیل F و M (روز)">
                      <input
                        className={fromLegacy('ltr')}
                        type="number"
                        min="30"
                        max="3650"
                        value={settings.lookback_days}
                        disabled={!canManage}
                        onChange={(e) => setSettings({ ...settings, lookback_days: Number(e.target.value || 730) })}
                      />
                    </Field>
                    <Field label="بازهٔ محاسبه تکرار و مبلغ">
                      <Select
                        value={settings.fm_window}
                        onChange={(value) => setSettings({ ...settings, fm_window: value })}
                        options={[
                          { value: 'lookback', label: 'همان بازهٔ بالا' },
                          { value: 'lifetime', label: 'کل خریدهای مشتری' },
                        ]}
                        disabled={!canManage}
                        label="بازه F/M"
                      />
                    </Field>
                    <Field label="منبع مبلغ (M)">
                      <Select
                        value={settings.monetary_field}
                        onChange={(value) => setSettings({ ...settings, monetary_field: value })}
                        options={[
                          { value: 'final_amount', label: 'مبلغ نهایی فاکتور' },
                          { value: 'paid_amount', label: 'مبلغ پرداخت‌شده' },
                        ]}
                        disabled={!canManage}
                        label="منبع مبلغ"
                      />
                    </Field>
                    {canManage && <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره اساس امتیاز'}</Button>}
                  </form>
                )}
              </Card>

              {settings?.score_method === 'threshold' && (
                <div className={fromLegacy('form')} style={{ display: 'grid', gap: 12, marginTop: 12 }}>
                  <ThresholdEditor
                    title="آستانه تازگی (R) — روز کمتر = امتیاز بیشتر"
                    kind="r"
                    rows={settings.r_thresholds}
                    onChange={(rows) => canManage && setSettings({ ...settings, r_thresholds: rows })}
                  />
                  <ThresholdEditor
                    title="آستانه تکرار (F)"
                    kind="f"
                    rows={settings.f_thresholds}
                    onChange={(rows) => canManage && setSettings({ ...settings, f_thresholds: rows })}
                  />
                  <ThresholdEditor
                    title="آستانه مبلغ (M)"
                    kind="m"
                    rows={settings.m_thresholds}
                    onChange={(rows) => canManage && setSettings({ ...settings, m_thresholds: rows })}
                  />
                </div>
              )}

              <Card
                title="بخش‌ها و اکشن‌ها"
                actions={canManage ? <Button onClick={openCreate}>+ بخش جدید</Button> : null}
              >
                <p className={fromLegacy('muted')}>
                  اولین بخش مطابق (از بالا به پایین) برنده است. امتیاز خالی یعنی همهٔ مقادیر آن شاخص.
                </p>
                {segments.length === 0 ? (
                  <EmptyState text="بخشی تعریف نشده است." />
                ) : (
                  <>
                    <div className={fromLegacy('table-wrap rfm-table-desktop')}>
                      <table className={fromLegacy('table')}>
                        <thead>
                          <tr>
                            <th>بخش</th>
                            <th>R / F / M</th>
                            <th>اکشن</th>
                            <th>پیامک خودکار</th>
                            <th>عملیات</th>
                          </tr>
                        </thead>
                        <tbody>
                          {segments.map((segment) => (
                            <tr key={segment.id}>
                              <td><Badge color={segment.color}>{segment.name}</Badge></td>
                              <td className="ltr">
                                R:{segment.r_scores.join(',') || '*'}
                                {' '}F:{segment.f_scores.join(',') || '*'}
                                {' '}M:{segment.m_scores.join(',') || '*'}
                              </td>
                              <td>{segment.action_title || segment.action_type_label}</td>
                              <td>{segment.auto_sms ? 'فعال' : 'خاموش'}</td>
                              <td className={fromLegacy('row-actions')}>
                                {canManage && (
                                  <>
                                    <button type="button" className={fromLegacy('link')} onClick={() => openEdit(segment)}>ویرایش</button>
                                    <button type="button" className={fromLegacy('link danger')} onClick={() => removeSegment(segment)}>حذف</button>
                                  </>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="rfm-cards-mobile">
                      {segments.map((segment) => (
                        <div key={segment.id} className={fromLegacy('m-card')}>
                          <div className={fromLegacy('m-card-head')}>
                            <Badge color={segment.color}>{segment.name}</Badge>
                            <span className={fromLegacy('muted')}>{segment.action_type_label}</span>
                          </div>
                          <p>{segment.action_title}</p>
                          {canManage && (
                            <div className={fromLegacy('m-card-actions')}>
                              <button type="button" className={fromLegacy('link')} onClick={() => openEdit(segment)}>ویرایش</button>
                              <button type="button" className={fromLegacy('link danger')} onClick={() => removeSegment(segment)}>حذف</button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Card>
            </>
          )}
        </>
      )}

      <Modal title={editing ? 'ویرایش بخش' : 'بخش جدید'} open={modalOpen} onClose={() => setModalOpen(false)} wide>
        <form onSubmit={saveSegment} className={fromLegacy('form')}>
          <Field label="نام بخش">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="رنگ">
            <input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
          </Field>
          <Field label="اولویت (عدد کمتر = زودتر بررسی می‌شود)">
            <input
              className={fromLegacy('ltr')}
              type="number"
              min="0"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value || 0) })}
            />
          </Field>
          <ScoreChecks label="امتیاز تازگی (R)" values={form.r_scores} onChange={(r_scores) => setForm({ ...form, r_scores })} />
          <ScoreChecks label="امتیاز تکرار (F)" values={form.f_scores} onChange={(f_scores) => setForm({ ...form, f_scores })} />
          <ScoreChecks label="امتیاز مبلغ (M)" values={form.m_scores} onChange={(m_scores) => setForm({ ...form, m_scores })} />
          <Field label="نوع اکشن">
            <Select
              value={form.action_type}
              onChange={(action_type) => setForm({ ...form, action_type })}
              options={ACTION_OPTIONS}
              label="نوع اکشن"
            />
          </Field>
          <Field label="عنوان اکشن برای تیم فروش">
            <input value={form.action_title} onChange={(e) => setForm({ ...form, action_title: e.target.value })} />
          </Field>
          <Field label="راهنمای اقدام">
            <textarea rows={3} value={form.action_body} onChange={(e) => setForm({ ...form, action_body: e.target.value })} />
          </Field>
          <Field label="توضیح بخش">
            <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <label className="rfm-score-chip">
            <input
              type="checkbox"
              checked={form.no_discount}
              onChange={(e) => setForm({ ...form, no_discount: e.target.checked })}
            />
            تخفیف ندهید
          </label>
          <label className="rfm-score-chip">
            <input
              type="checkbox"
              checked={form.auto_sms}
              onChange={(e) => setForm({ ...form, auto_sms: e.target.checked })}
            />
            ارسال پیامک خودکار پس از محاسبه شبانه
          </label>
          <Field label="قالب پیامک — متغیرها: name, shop_name, phone, code, rfm, segment">
            <textarea rows={3} value={form.sms_template} onChange={(e) => setForm({ ...form, sms_template: e.target.value })} />
          </Field>
          <Field label="فاصلهٔ ارسال مجدد پیامک (روز)">
            <input
              className={fromLegacy('ltr')}
              type="number"
              min="0"
              value={form.sms_cooldown_days}
              onChange={(e) => setForm({ ...form, sms_cooldown_days: Number(e.target.value || 0) })}
            />
          </Field>
          <label className="rfm-score-chip">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            بخش فعال باشد
          </label>
          <Button type="submit">ذخیره بخش</Button>
        </form>
      </Modal>
    </div>
  )
}
