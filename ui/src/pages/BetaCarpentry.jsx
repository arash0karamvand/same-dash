import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaCarpentryApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatMoney } from '../utils/format'
import { formatJalali, todayIso } from '../utils/jalali'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'
import { BETA_WORKSHOP_KIND, useBetaOptions } from '../hooks/useBetaOptions'

const MODULES = [
  { key: 'tools', label: 'ابزار و تجهیزات', countKey: 'tools' },
  { key: 'wood', label: 'خرید چوب و MDF', countKey: 'wood' },
  { key: 'services', label: 'خدمات برون‌سازمانی', countKey: 'services' },
  { key: 'freight', label: 'باربری و حمل', countKey: 'freight' },
  { key: 'attendance', label: 'تردد پرسنل', countKey: 'attendance' },
]

const EMPTY_TOOL = { name: '', category: '', workshop_id: '', status: 'active', quantity: '1', purchase_date: '', value: '', note: '' }
const EMPTY_WOOD = { supplier: '', material_type: '', wood_type: '', quantity: '', unit: 'متر', unit_cost: '', total_cost: '', purchase_date: todayIso(), workshop_id: '', invoice_ref: '', note: '' }
const EMPTY_SERVICE = { service_type: '', provider: '', workshop_id: '', carpentry_order_id: '', amount: '', service_date: todayIso(), description: '' }
const EMPTY_FREIGHT = { destination: '', driver_name: '', workshop_id: '', carpentry_order_id: '', cost: '', sent_date: todayIso(), note: '' }
const EMPTY_ATTENDANCE = { workshop_id: '', person_name: '', visit_date: todayIso(), check_in: '', check_out: '', note: '' }

const TOOL_STATUS_OPTS = [
  { value: 'active', label: 'فعال' },
  { value: 'maintenance', label: 'در تعمیر' },
  { value: 'retired', label: 'اسقاط' },
]

function scopeParams(workshopScope) {
  if (!workshopScope) return {}
  if (workshopScope === 'internal' || workshopScope === 'satellite') return { workshop_kind: workshopScope }
  return { workshop_id: Number(workshopScope) }
}

export default function BetaCarpentry() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const betaOptions = useBetaOptions()
  const canManage = hasPermission(user, 'manage_beta_carpentry')

  const [module, setModule] = useState('tools')
  const [workshopScope, setWorkshopScope] = useState('')
  const [stats, setStats] = useState({ summary: {}, modules: {} })
  const [workshops, setWorkshops] = useState([])
  const [rows, setRows] = useState([])
  const [orderPicker, setOrderPicker] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const [editingWorkshop, setEditingWorkshop] = useState(null)
  const [workshopForm, setWorkshopForm] = useState({ name: '', kind: '', is_active: true })
  const [modal, setModal] = useState(null)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({})

  const scope = useMemo(() => scopeParams(workshopScope), [workshopScope])
  const workshopKindOpts = useMemo(() => betaOptions(BETA_WORKSHOP_KIND, stats.workshop_kinds), [betaOptions, stats.workshop_kinds])
  const workshopOpts = useMemo(() => workshops.map((w) => ({ value: String(w.id), label: w.name })), [workshops])
  const orderOpts = useMemo(() => orderPicker.map((r) => ({ value: String(r.id), label: r.code })), [orderPicker])

  const loadModuleRows = useCallback(async () => {
    const q = { search: search.trim(), limit: 100, ...scope }
    if (module === 'tools') return (await betaCarpentryApi.tools(q)).results || []
    if (module === 'wood') return (await betaCarpentryApi.woodPurchases(q)).results || []
    if (module === 'services') return (await betaCarpentryApi.services(q)).results || []
    if (module === 'freight') return (await betaCarpentryApi.freight(q)).results || []
    if (module === 'attendance') return (await betaCarpentryApi.attendance(q)).results || []
    return []
  }, [module, search, scope])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, w, list, orders] = await Promise.all([
        betaCarpentryApi.stats(scope),
        betaCarpentryApi.workshops(),
        loadModuleRows(),
        betaCarpentryApi.orders({ ...scope, limit: 200 }),
      ])
      setStats(s || { summary: {}, modules: {} })
      setWorkshops(w.results || w || [])
      setRows(list)
      setOrderPicker(orders.results || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [scope, loadModuleRows])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    const ws = workshopScope && !['internal', 'satellite'].includes(workshopScope) ? workshopScope : (workshops[0] ? String(workshops[0].id) : '')
    const map = {
      tools: { ...EMPTY_TOOL, workshop_id: ws },
      wood: { ...EMPTY_WOOD, workshop_id: ws },
      services: { ...EMPTY_SERVICE, workshop_id: ws },
      freight: { ...EMPTY_FREIGHT, workshop_id: ws },
      attendance: { ...EMPTY_ATTENDANCE, workshop_id: ws },
    }
    setEditing(null)
    setForm(map[module] || {})
    setModal(module)
  }

  const openEdit = (row) => {
    setEditing(row)
    if (module === 'tools') setForm({ name: row.name, category: row.category, workshop_id: row.workshop_id ? String(row.workshop_id) : '', status: row.status, quantity: String(row.quantity), purchase_date: row.purchase_date || '', value: String(row.value || ''), note: row.note || '' })
    if (module === 'wood') setForm({ supplier: row.supplier, material_type: row.material_type, wood_type: row.wood_type, quantity: String(row.quantity), unit: row.unit, unit_cost: String(row.unit_cost), total_cost: String(row.total_cost), purchase_date: row.purchase_date || '', workshop_id: row.workshop_id ? String(row.workshop_id) : '', invoice_ref: row.invoice_ref, note: row.note || '' })
    if (module === 'services') setForm({ service_type: row.service_type, provider: row.provider, workshop_id: row.workshop_id ? String(row.workshop_id) : '', carpentry_order_id: row.carpentry_order_id ? String(row.carpentry_order_id) : '', amount: String(row.amount), service_date: row.service_date || '', description: row.description || '' })
    if (module === 'freight') setForm({ destination: row.destination, driver_name: row.driver_name, workshop_id: row.workshop_id ? String(row.workshop_id) : '', carpentry_order_id: row.carpentry_order_id ? String(row.carpentry_order_id) : '', cost: String(row.cost), sent_date: row.sent_date || '', note: row.note || '' })
    if (module === 'attendance') setForm({ workshop_id: String(row.workshop_id), person_name: row.person_name, visit_date: row.visit_date || '', check_in: row.check_in || '', check_out: row.check_out || '', note: row.note || '' })
    setModal(module)
  }

  const save = async () => {
    setSaving(true)
    try {
      if (modal === 'tools') {
        const payload = { ...form, workshop_id: form.workshop_id ? Number(form.workshop_id) : null, quantity: Number(form.quantity || 1), value: form.value }
        if (editing) await betaCarpentryApi.updateTool(editing.id, payload)
        else await betaCarpentryApi.createTool(payload)
      } else if (modal === 'wood') {
        const payload = { ...form, workshop_id: form.workshop_id ? Number(form.workshop_id) : null, quantity: form.quantity, unit_cost: form.unit_cost, total_cost: form.total_cost }
        if (editing) await betaCarpentryApi.updateWoodPurchase(editing.id, payload)
        else await betaCarpentryApi.createWoodPurchase(payload)
      } else if (modal === 'services') {
        const payload = { ...form, workshop_id: form.workshop_id ? Number(form.workshop_id) : null, carpentry_order_id: form.carpentry_order_id ? Number(form.carpentry_order_id) : null, amount: form.amount }
        if (editing) await betaCarpentryApi.updateService(editing.id, payload)
        else await betaCarpentryApi.createService(payload)
      } else if (modal === 'freight') {
        const payload = { ...form, workshop_id: form.workshop_id ? Number(form.workshop_id) : null, carpentry_order_id: form.carpentry_order_id ? Number(form.carpentry_order_id) : null, cost: form.cost }
        if (editing) await betaCarpentryApi.updateFreight(editing.id, payload)
        else await betaCarpentryApi.createFreight(payload)
      } else if (modal === 'attendance') {
        const payload = { ...form, workshop_id: Number(form.workshop_id) }
        if (editing) await betaCarpentryApi.updateAttendance(editing.id, payload)
        else await betaCarpentryApi.createAttendance(payload)
      } else if (modal === 'workshop') {
        if (editingWorkshop) await betaCarpentryApi.updateWorkshop(editingWorkshop.id, workshopForm)
        else await betaCarpentryApi.createWorkshop(workshopForm)
        setEditingWorkshop(null)
      }
      setModal(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const openWorkshopModal = (workshop = null) => {
    setEditingWorkshop(workshop)
    setWorkshopForm(workshop
      ? { name: workshop.name, kind: workshop.kind, is_active: workshop.is_active !== false }
      : { name: '', kind: workshopKindOpts[0]?.value || '', is_active: true })
    setModal('workshop')
  }

  const removeWorkshop = async () => {
    const w = workshops.find((item) => String(item.id) === workshopScope)
    if (!w || !(await confirm({ title: 'حذف واحد نجاری', message: `«${w.name}» حذف شود؟` }))) return
    try {
      await betaCarpentryApi.removeWorkshop(w.id)
      setWorkshopScope('')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const removeRow = async (row) => {
    const label = row.code || row.name || row.person_name || row.id
    if (!(await confirm({ title: 'حذف رکورد', message: `${label} حذف شود؟` }))) return
    try {
      if (module === 'tools') await betaCarpentryApi.removeTool(row.id)
      else if (module === 'wood') await betaCarpentryApi.removeWoodPurchase(row.id)
      else if (module === 'services') await betaCarpentryApi.removeService(row.id)
      else if (module === 'freight') await betaCarpentryApi.removeFreight(row.id)
      else if (module === 'attendance') await betaCarpentryApi.removeAttendance(row.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const summary = stats.summary || {}
  const moduleCounts = stats.modules || {}
  const activeModule = MODULES.find((m) => m.key === module)

  const renderTable = () => {
    if (loading) return <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
    if (rows.length === 0) return <EmptyState text="رکوردی در این بخش ثبت نشده." />

    if (module === 'tools') {
      return (
        <div className={fromLegacy('table-wrap')}>
          <table className={fromLegacy('data-table')}>
            <thead><tr><th>کد</th><th>نام</th><th>دسته</th><th>کارگاه</th><th>تعداد</th><th>ارزش</th><th>وضعیت</th><th>عملیات</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td><td>{r.name}</td><td>{r.category || '—'}</td><td>{r.workshop_name || '—'}</td>
                  <td>{r.quantity}</td><td>{formatMoney(r.value)}</td><td><Badge>{r.status_display}</Badge></td>
                  <td>{canManage && (<><Button variant="ghost" size="sm" onClick={() => openEdit(r)}>ویرایش</Button><Button variant="ghost" size="sm" onClick={() => removeRow(r)}>حذف</Button></>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    if (module === 'wood') {
      return (
        <div className={fromLegacy('table-wrap')}>
          <table className={fromLegacy('data-table')}>
            <thead><tr><th>کد</th><th>تامین‌کننده</th><th>متریال</th><th>مقدار</th><th>مبلغ</th><th>تاریخ</th><th>کارگاه</th><th>عملیات</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td><td>{r.supplier || '—'}</td><td>{r.material_type || r.wood_type || '—'}</td>
                  <td>{r.quantity} {r.unit}</td><td>{formatMoney(r.total_cost)}</td>
                  <td>{r.purchase_date ? formatJalali(r.purchase_date) : '—'}</td><td>{r.workshop_name || '—'}</td>
                  <td>{canManage && (<><Button variant="ghost" size="sm" onClick={() => openEdit(r)}>ویرایش</Button><Button variant="ghost" size="sm" onClick={() => removeRow(r)}>حذف</Button></>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    if (module === 'services') {
      return (
        <div className={fromLegacy('table-wrap')}>
          <table className={fromLegacy('data-table')}>
            <thead><tr><th>کد</th><th>نوع</th><th>ارائه‌دهنده</th><th>دستور</th><th>مبلغ</th><th>تاریخ</th><th>عملیات</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td><td>{r.service_type || '—'}</td><td>{r.provider || '—'}</td>
                  <td>{r.carpentry_order_code || '—'}</td><td>{formatMoney(r.amount)}</td>
                  <td>{r.service_date ? formatJalali(r.service_date) : '—'}</td>
                  <td>{canManage && (<><Button variant="ghost" size="sm" onClick={() => openEdit(r)}>ویرایش</Button><Button variant="ghost" size="sm" onClick={() => removeRow(r)}>حذف</Button></>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    if (module === 'freight') {
      return (
        <div className={fromLegacy('table-wrap')}>
          <table className={fromLegacy('data-table')}>
            <thead><tr><th>کد</th><th>مقصد</th><th>راننده</th><th>دستور</th><th>هزینه</th><th>تاریخ</th><th>عملیات</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td><td>{r.destination}</td><td>{r.driver_name || '—'}</td>
                  <td>{r.carpentry_order_code || '—'}</td><td>{formatMoney(r.cost)}</td>
                  <td>{r.sent_date ? formatJalali(r.sent_date) : '—'}</td>
                  <td>{canManage && (<><Button variant="ghost" size="sm" onClick={() => openEdit(r)}>ویرایش</Button><Button variant="ghost" size="sm" onClick={() => removeRow(r)}>حذف</Button></>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    return (
      <div className={fromLegacy('table-wrap')}>
        <table className={fromLegacy('data-table')}>
          <thead><tr><th>کارگاه</th><th>پرسنل</th><th>تاریخ</th><th>ورود</th><th>خروج</th><th>عملیات</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.workshop_name}</td><td>{r.person_name}</td>
                <td>{r.visit_date ? formatJalali(r.visit_date) : '—'}</td>
                <td>{r.check_in || '—'}</td><td>{r.check_out || '—'}</td>
                <td>{canManage && (<><Button variant="ghost" size="sm" onClick={() => openEdit(r)}>ویرایش</Button><Button variant="ghost" size="sm" onClick={() => removeRow(r)}>حذف</Button></>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>واحدهای نجاری (بتا)</h1>
          <p className={fromLegacy('muted')}>
            مدیریت چندکارگاهی — ابزار، خرید چوب، خدمات برون‌سازمانی، باربری و تردد پرسنل
          </p>
        </div>
        {canManage && (
          <div className={fromLegacy('row')}>
            {workshopScope && !['internal', 'satellite', ''].includes(workshopScope) && (
              <>
                <Button variant="ghost" onClick={() => openWorkshopModal(workshops.find((w) => String(w.id) === workshopScope))}>ویرایش واحد</Button>
                <Button variant="ghost" onClick={removeWorkshop}>حذف واحد</Button>
              </>
            )}
            <Button variant="ghost" onClick={() => openWorkshopModal()}>+ افزودن واحد نجاری</Button>
            <Button onClick={openCreate}>+ ثبت {activeModule?.label}</Button>
          </div>
        )}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <div className={fromLegacy('workflow-filter-tabs')} style={{ marginBottom: 12 }}>
        <button type="button" className={fromLegacy(`workflow-filter-tab ${workshopScope === '' ? 'active' : ''}`)} onClick={() => setWorkshopScope('')}>
          همه واحدهای نجاری ({stats.workshops ?? 0})
        </button>
        {workshopKindOpts.map((opt) => (
          <button key={opt.value} type="button" className={fromLegacy(`workflow-filter-tab ${workshopScope === opt.value ? 'active' : ''}`)} onClick={() => setWorkshopScope(opt.value)}>{opt.label}</button>
        ))}
        {workshops.map((w) => (
          <button key={w.id} type="button" className={fromLegacy(`workflow-filter-tab ${workshopScope === String(w.id) ? 'active' : ''}`)} onClick={() => setWorkshopScope(String(w.id))}>
            {w.name}
          </button>
        ))}
      </div>

      <div className={fromLegacy('stat-grid')}>
        <StatCard label="هزینه باربری اقماری" value={formatMoney(summary.satellite_freight_cost || 0)} />
        <StatCard label="ابزار و دستگاه" value={summary.tools_count ?? 0} hint="دستگاه" />
        <StatCard label="خرید چوب و MDF" value={formatMoney(summary.wood_purchase_total || 0)} />
      </div>

      <div className={fromLegacy('workflow-filter-tabs')} style={{ marginBottom: 12, flexWrap: 'wrap' }}>
        {MODULES.map((m) => (
          <button key={m.key} type="button" className={fromLegacy(`workflow-filter-tab ${module === m.key ? 'active' : ''}`)} onClick={() => setModule(m.key)}>
            {m.label} ({moduleCounts[m.countKey] ?? 0})
          </button>
        ))}
      </div>

      <FilterBar>
        <Field label="جستجو">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو…" />
        </Field>
      </FilterBar>

      <Card title={`${activeModule?.label || ''} — لیست رکوردها`}>
        {renderTable()}
      </Card>

      <Modal title={editingWorkshop ? 'ویرایش واحد نجاری' : 'افزودن واحد نجاری'} open={modal === 'workshop'} onClose={() => { setModal(null); setEditingWorkshop(null) }}>
        <Field label="نام واحد"><input value={workshopForm.name} onChange={(e) => setWorkshopForm({ ...workshopForm, name: e.target.value })} /></Field>
        <Field label="نوع"><Select value={workshopForm.kind} onChange={(v) => setWorkshopForm({ ...workshopForm, kind: v })} options={workshopKindOpts} /></Field>
        <Field label="وضعیت">
          <label className={fromLegacy('checkbox-row')}>
            <input type="checkbox" checked={workshopForm.is_active} onChange={(e) => setWorkshopForm({ ...workshopForm, is_active: e.target.checked })} />
            <span>واحد فعال است</span>
          </label>
        </Field>
        <Button disabled={saving} onClick={save}>ذخیره واحد</Button>
      </Modal>

      <Modal title={editing ? 'ویرایش ابزار' : 'ثبت ابزار'} open={modal === 'tools'} onClose={() => setModal(null)}>
        <Field label="نام"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="دسته"><input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></Field>
        <Field label="کارگاه"><Select value={form.workshop_id} onChange={(v) => setForm({ ...form, workshop_id: v })} options={[{ value: '', label: '—' }, ...workshopOpts]} /></Field>
        <Field label="وضعیت"><Select value={form.status} onChange={(v) => setForm({ ...form, status: v })} options={TOOL_STATUS_OPTS} /></Field>
        <Field label="تعداد"><input className={fromLegacy('ltr')} type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
        <Field label="ارزش"><MoneyInput value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} /></Field>
        <Field label="تاریخ تحویل"><PersianDateInput value={form.purchase_date} onChange={(v) => setForm({ ...form, purchase_date: v })} /></Field>
        <Field label="توضیحات"><textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        <Button disabled={saving} onClick={save}>ذخیره</Button>
      </Modal>

      <Modal title={editing ? 'ویرایش خرید' : 'ثبت خرید چوب'} open={modal === 'wood'} onClose={() => setModal(null)} wide>
        <Field label="تامین‌کننده"><input value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} /></Field>
        <Field label="نوع متریال"><input value={form.material_type} onChange={(e) => setForm({ ...form, material_type: e.target.value })} placeholder="چوب، MDF…" /></Field>
        <Field label="جنس"><input value={form.wood_type} onChange={(e) => setForm({ ...form, wood_type: e.target.value })} /></Field>
        <Field label="مقدار"><input className={fromLegacy('ltr')} type="number" step="0.01" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
        <Field label="واحد"><input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} placeholder="متر، عدد…" /></Field>
        <Field label="بهای واحد"><MoneyInput value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} /></Field>
        <Field label="مبلغ کل"><MoneyInput value={form.total_cost} onChange={(e) => setForm({ ...form, total_cost: e.target.value })} /></Field>
        <Field label="شماره فاکتور"><input value={form.invoice_ref} onChange={(e) => setForm({ ...form, invoice_ref: e.target.value })} /></Field>
        <Field label="کارگاه"><Select value={form.workshop_id} onChange={(v) => setForm({ ...form, workshop_id: v })} options={[{ value: '', label: '—' }, ...workshopOpts]} /></Field>
        <Field label="تاریخ"><PersianDateInput value={form.purchase_date} onChange={(v) => setForm({ ...form, purchase_date: v })} /></Field>
        <Field label="توضیحات"><textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        <Button disabled={saving} onClick={save}>ذخیره</Button>
      </Modal>

      <Modal title={editing ? 'ویرایش خدمت' : 'ثبت خدمت'} open={modal === 'services'} onClose={() => setModal(null)} wide>
        <Field label="نوع خدمت"><input value={form.service_type} onChange={(e) => setForm({ ...form, service_type: e.target.value })} placeholder="خراطی، CNC…" /></Field>
        <Field label="ارائه‌دهنده"><input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} /></Field>
        <Field label="کارگاه"><Select value={form.workshop_id} onChange={(v) => setForm({ ...form, workshop_id: v })} options={[{ value: '', label: '—' }, ...workshopOpts]} /></Field>
        <Field label="دستور مرتبط"><Select value={form.carpentry_order_id} onChange={(v) => setForm({ ...form, carpentry_order_id: v })} options={[{ value: '', label: '—' }, ...orderOpts]} /></Field>
        <Field label="مبلغ"><MoneyInput value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
        <Field label="تاریخ"><PersianDateInput value={form.service_date} onChange={(v) => setForm({ ...form, service_date: v })} /></Field>
        <Field label="شرح"><textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <Button disabled={saving} onClick={save}>ذخیره</Button>
      </Modal>

      <Modal title={editing ? 'ویرایش باربری' : 'ثبت باربری'} open={modal === 'freight'} onClose={() => setModal(null)}>
        <Field label="مقصد"><input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} /></Field>
        <Field label="راننده / باربری"><input value={form.driver_name} onChange={(e) => setForm({ ...form, driver_name: e.target.value })} /></Field>
        <Field label="کارگاه"><Select value={form.workshop_id} onChange={(v) => setForm({ ...form, workshop_id: v })} options={[{ value: '', label: '—' }, ...workshopOpts]} /></Field>
        <Field label="دستور"><Select value={form.carpentry_order_id} onChange={(v) => setForm({ ...form, carpentry_order_id: v })} options={[{ value: '', label: '—' }, ...orderOpts]} /></Field>
        <Field label="هزینه"><MoneyInput value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></Field>
        <Field label="تاریخ"><PersianDateInput value={form.sent_date} onChange={(v) => setForm({ ...form, sent_date: v })} /></Field>
        <Field label="توضیحات"><textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        <Button disabled={saving} onClick={save}>ذخیره</Button>
      </Modal>

      <Modal title={editing ? 'ویرایش تردد' : 'ثبت تردد'} open={modal === 'attendance'} onClose={() => setModal(null)}>
        <Field label="کارگاه"><Select value={form.workshop_id} onChange={(v) => setForm({ ...form, workshop_id: v })} options={workshopOpts} /></Field>
        <Field label="نام پرسنل"><input value={form.person_name} onChange={(e) => setForm({ ...form, person_name: e.target.value })} /></Field>
        <Field label="تاریخ"><PersianDateInput value={form.visit_date} onChange={(v) => setForm({ ...form, visit_date: v })} /></Field>
        <Field label="ورود"><input className={fromLegacy('ltr')} type="time" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} /></Field>
        <Field label="خروج"><input className={fromLegacy('ltr')} type="time" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} /></Field>
        <Field label="توضیحات"><textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        <Button disabled={saving} onClick={save}>ذخیره</Button>
      </Modal>
    </div>
  )
}
