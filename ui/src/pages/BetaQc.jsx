import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaQcApi } from '../api/client'
import { BetaChipNav, BetaSegmentNav } from '../components/BetaSegmentNav'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useBetaSaleSources } from '../hooks/useBetaSaleSources'
import { formatJalali, todayIso, toPersianDigits } from '../utils/jalali'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'
import { BETA_QC_GRADE, BETA_QC_STATUS, useBetaOptions } from '../hooks/useBetaOptions'

const EMPTY = {
  sale_id: '',
  order_ref: '',
  buyer_name: '',
  invoice_ref: '',
  origin: '',
  product_name: '',
  requirements: '',
  quantity: '1',
  wood_color: '',
  fabric_color: '',
  grade: '',
  scan_url: '',
  entered_at: todayIso(),
}

export default function BetaQc() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const betaOptions = useBetaOptions()
  const { saleOptions, applySale } = useBetaSaleSources()
  const canManage = hasPermission(user, 'manage_beta_qc')
  const [stats, setStats] = useState({})
  const [items, setItems] = useState([])
  const [listTotal, setListTotal] = useState(0)
  const [archive, setArchive] = useState('0')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [evalItem, setEvalItem] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [evalForm, setEvalForm] = useState({ status: '', grade: '', scan_url: '', requirements: '' })
  const [saving, setSaving] = useState(false)

  const statusOpts = useMemo(() => betaOptions(BETA_QC_STATUS, stats.statuses), [betaOptions, stats.statuses])
  const gradeOpts = useMemo(() => betaOptions(BETA_QC_GRADE, stats.grades), [betaOptions, stats.grades])
  const archiveStatus = stats.archive_status || ''
  const currentStatusOpts = useMemo(
    () => statusOpts.filter((opt) => opt.value !== archiveStatus),
    [statusOpts, archiveStatus],
  )

  const archiveItems = useMemo(() => [
    { key: '0', label: 'کارهای جاری', count: stats.current ?? 0, hint: 'در انتظار بررسی' },
    { key: '1', label: 'آرشیو و تاییدشده', count: stats.approved ?? 0, hint: 'سوابق QC' },
  ], [stats])

  const statusChipItems = useMemo(() => [
    { key: '', label: 'همه جاری', count: stats.current ?? 0 },
    ...currentStatusOpts.map((opt) => ({
      key: opt.value,
      label: opt.label,
      count: stats.by_status?.[opt.value] ?? 0,
      accent: opt.meta?.color,
    })),
  ], [currentStatusOpts, stats])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const searchTrim = search.trim()
    try {
      const [s, list] = await Promise.all([
        betaQcApi.stats({ search: searchTrim }),
        betaQcApi.list({ search: searchTrim, archive, status, limit: 100 }),
      ])
      setStats(s || {})
      setItems(list.results || [])
      setListTotal(list.total ?? 0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search, archive, status])

  useEffect(() => { load() }, [load])

  const grouped = useMemo(() => {
    const map = {}
    for (const item of items) {
      const key = item.order_ref || 'بدون سفارش'
      if (!map[key]) map[key] = []
      map[key].push(item)
    }
    return map
  }, [items])

  const switchArchive = (next) => {
    setArchive(next)
    setStatus('')
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, entered_at: todayIso() })
    setCreateOpen(true)
  }

  const openEdit = (item) => {
    setEditing(item)
    setForm({
      sale_id: item.sale_id ? String(item.sale_id) : '',
      order_ref: item.order_ref || '',
      buyer_name: item.buyer_name || '',
      invoice_ref: item.invoice_ref || '',
      origin: item.origin || '',
      product_name: item.product_name || '',
      requirements: item.requirements || '',
      quantity: String(item.quantity || 1),
      wood_color: item.wood_color || '',
      fabric_color: item.fabric_color || '',
      grade: item.grade || '',
      scan_url: item.scan_url || '',
      entered_at: item.entered_at || todayIso(),
    })
    setCreateOpen(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const payload = {
        ...form,
        sale_id: form.sale_id ? Number(form.sale_id) : null,
        quantity: Number(form.quantity || 1),
      }
      if (editing) await betaQcApi.update(editing.id, payload)
      else await betaQcApi.create(payload)
      setCreateOpen(false)
      setEditing(null)
      setForm({ ...EMPTY, entered_at: todayIso() })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeItem = async (item) => {
    if (!(await confirm({ title: 'حذف بازرسی', message: `${item.code} حذف شود؟` }))) return
    try {
      await betaQcApi.remove(item.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const evaluate = async () => {
    if (!evalItem) return
    setSaving(true)
    try {
      await betaQcApi.evaluate(evalItem.id, evalForm)
      setEvalItem(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>واحد کنترل کیفیت (QC) — بتا</h1>
          <p className={fromLegacy('muted')}>
            بررسی استانداردهای کیفی به تفکیک هر محصول، تفکیک کارهای جاری از آرشیو و انتقال به ترخیص
          </p>
        </div>
        {canManage && (
          <Button onClick={openCreate}>
            + ثبت قلم بازرسی
          </Button>
        )}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <BetaSegmentNav
        label="بخش QC"
        value={archive}
        onChange={switchArchive}
        items={archiveItems}
      />

      <div className={fromLegacy('stat-grid')}>
        {archive === '0' ? (
          currentStatusOpts.map((opt) => (
            <StatCard
              key={opt.value}
              label={opt.label}
              value={stats.by_status?.[opt.value] ?? 0}
              accent={opt.meta?.color}
              active={status === opt.value}
              onClick={() => setStatus(status === opt.value ? '' : opt.value)}
            />
          ))
        ) : (
          <StatCard label="سوابق تاییدشده" value={stats.approved ?? 0} accent="var(--success)" active />
        )}
        <StatCard label="کل بازرسی‌های ثبت‌شده" value={stats.total ?? 0} />
      </div>

      {archive === '0' && (
        <BetaChipNav
          label="وضعیت بررسی"
          value={status}
          onChange={setStatus}
          items={statusChipItems}
        />
      )}

      <FilterBar>
        <Field label="جستجو">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجوی نام محصول، شماره سفارش، مشتری، رنگ چوب، کد پارچه…"
          />
        </Field>
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : items.length === 0 ? (
        <EmptyState text={archive === '0' ? 'قلمی در صف QC نیست' : 'سابقه‌ای در آرشیو نیست'} />
      ) : (
        <>
        {listTotal > 0 && (
          <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
            {toPersianDigits(listTotal)} رکورد
            {listTotal > items.length && ` — نمایش ${toPersianDigits(items.length)} مورد اول`}
          </p>
        )}
        {Object.entries(grouped).map(([orderRef, rows]) => (
          <Card key={orderRef} className={fromLegacy('beta-qc-order-card')}>
            <div className={fromLegacy('beta-qc-order-head')}>
              <div>
                <h3>{orderRef}</h3>
                <span className={fromLegacy('muted small')}>
                  {rows.length} قلم — خریدار: {rows[0].buyer_name || '—'}
                </span>
              </div>
              <Badge>{archive === '0' ? 'جاری' : 'آرشیو'}</Badge>
            </div>
            <div className={fromLegacy('beta-qc-order-meta')}>
              <span>مبدا ساخت: {rows[0].origin || '—'}</span>
              <span>تاریخ ورود: {rows[0].entered_at ? formatJalali(rows[0].entered_at) : '—'}</span>
              {rows[0].invoice_ref && <span>فاکتور: {rows[0].invoice_ref}</span>}
            </div>
            <div className={fromLegacy('table-wrap')}>
              <table className={fromLegacy('data-table')}>
                <thead>
                  <tr>
                    <th>کد بازرسی</th>
                    <th>محصول و مشخصات</th>
                    <th>تیراژ</th>
                    <th>رنگ چوب و پارچه</th>
                    <th>وضعیت</th>
                    <th>گرید</th>
                    <th>برگه اسکن</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item) => (
                    <tr key={item.id}>
                      <td>{item.code}</td>
                      <td>
                        {item.product_name}
                        {item.requirements && <div className={fromLegacy('muted small')}>{item.requirements}</div>}
                      </td>
                      <td>{item.quantity} عدد</td>
                      <td>
                        چوب: {item.wood_color || '—'}
                        <div className={fromLegacy('muted small')}>پارچه: {item.fabric_color || '—'}</div>
                      </td>
                      <td>
                        <Badge color={statusOpts.find((s) => s.value === item.status)?.meta?.color}>
                          {item.status_display}
                        </Badge>
                      </td>
                      <td>{item.grade_display || '—'}</td>
                      <td>
                        {item.scan_url ? (
                          <a href={item.scan_url} target="_blank" rel="noreferrer">مشاهده برگه</a>
                        ) : 'بارگذاری نشده'}
                      </td>
                      <td>
                        {canManage && (
                          <div className={fromLegacy('row')}>
                            {item.status !== archiveStatus && (
                              <Button
                                variant="ghost"
                                onClick={() => {
                                  setEvalItem(item)
                                  setEvalForm({
                                    status: archiveStatus || statusOpts[0]?.value || '',
                                    grade: item.grade || gradeOpts[0]?.value || '',
                                    scan_url: item.scan_url || '',
                                    requirements: item.requirements || '',
                                  })
                                }}
                              >
                                ثبت ارزیابی
                              </Button>
                            )}
                            <Button variant="ghost" size="sm" onClick={() => openEdit(item)}>ویرایش</Button>
                            <Button variant="ghost" size="sm" onClick={() => removeItem(item)}>حذف</Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))}
        </>
      )}

      <Modal title={editing ? `ویرایش ${editing.code}` : 'ثبت قلم بازرسی'} open={createOpen} onClose={() => { setCreateOpen(false); setEditing(null) }} wide>
        <Field label="سفارش کارخانه">
          <Select value={form.sale_id} onChange={(v) => setForm(applySale(v, form))} options={saleOptions} />
        </Field>
        <Field label="شماره سفارش">
          <input value={form.order_ref} onChange={(e) => setForm({ ...form, order_ref: e.target.value })} />
        </Field>
        <Field label="خریدار">
          <input value={form.buyer_name} onChange={(e) => setForm({ ...form, buyer_name: e.target.value })} />
        </Field>
        <Field label="فاکتور">
          <input value={form.invoice_ref} onChange={(e) => setForm({ ...form, invoice_ref: e.target.value })} />
        </Field>
        <Field label="مبدا ساخت">
          <input list="beta-qc-origins" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} />
          <datalist id="beta-qc-origins">
            {(stats.origin_options || []).map((o) => <option key={o} value={o} />)}
          </datalist>
        </Field>
        <Field label="محصول">
          <input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} />
        </Field>
        <Field label="الزامات">
          <textarea rows={3} value={form.requirements} onChange={(e) => setForm({ ...form, requirements: e.target.value })} />
        </Field>
        <Field label="تیراژ">
          <input className={fromLegacy('ltr')} type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        </Field>
        <Field label="رنگ چوب">
          <input list="beta-qc-wood-colors" value={form.wood_color} onChange={(e) => setForm({ ...form, wood_color: e.target.value })} />
          <datalist id="beta-qc-wood-colors">
            {(stats.wood_color_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="پارچه">
          <input list="beta-qc-fabric-colors" value={form.fabric_color} onChange={(e) => setForm({ ...form, fabric_color: e.target.value })} />
          <datalist id="beta-qc-fabric-colors">
            {(stats.fabric_color_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="گرید">
          <Select value={form.grade} onChange={(v) => setForm({ ...form, grade: v })} options={[{ value: '', label: 'بدون گرید' }, ...gradeOpts]} />
        </Field>
        <Field label="تاریخ ورود به QC">
          <PersianDateInput value={form.entered_at} onChange={(v) => setForm({ ...form, entered_at: v })} />
        </Field>
        <Field label="آدرس برگه اسکن">
          <input value={form.scan_url} onChange={(e) => setForm({ ...form, scan_url: e.target.value })} placeholder="https://…" />
        </Field>
        <Button disabled={saving} onClick={save}>{editing ? 'ذخیره تغییرات' : 'ثبت قلم'}</Button>
      </Modal>

      <Modal title={evalItem ? `ارزیابی ${evalItem.code}` : 'ارزیابی'} open={Boolean(evalItem)} onClose={() => setEvalItem(null)}>
        <Field label="وضعیت بررسی">
          <Select
            value={evalForm.status}
            onChange={(v) => setEvalForm({ ...evalForm, status: v })}
            options={statusOpts}
          />
        </Field>
        <Field label="گرید">
          <Select
            value={evalForm.grade}
            onChange={(v) => setEvalForm({ ...evalForm, grade: v })}
            options={[{ value: '', label: 'بدون گرید' }, ...gradeOpts]}
          />
        </Field>
        <Field label="الزامات">
          <textarea rows={3} value={evalForm.requirements} onChange={(e) => setEvalForm({ ...evalForm, requirements: e.target.value })} />
        </Field>
        <Field label="آدرس برگه اسکن">
          <input value={evalForm.scan_url} onChange={(e) => setEvalForm({ ...evalForm, scan_url: e.target.value })} placeholder="https://…" />
        </Field>
        <Button disabled={saving} onClick={evaluate}>ثبت ارزیابی</Button>
      </Modal>
    </div>
  )
}
