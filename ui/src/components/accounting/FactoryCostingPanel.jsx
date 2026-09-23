import { useCallback, useEffect, useState } from 'react'
import { Button, Card, EmptyState, Field } from '../ui'
import { fromLegacy } from '../../styles/tw'
import { formatNumber } from '../../utils/format'

const COST_TABS = [
  { id: 'cost-centers', label: 'مراکز هزینه' },
  { id: 'overhead', label: 'تسهیم سربار' },
  { id: 'wip-close', label: 'کالای در جریان ساخت' },
  { id: 'spoilage', label: 'ضایعات' },
]

const EMPTY_CENTER = {
  code: '',
  name: '',
  kind: 'production',
  allocation_base: 'machine_hours',
  base_quantity: '',
  branch: '',
}

export default function FactoryCostingPanel({ api, activeTab, onTabChange, canCreate }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [centerForm, setCenterForm] = useState(EMPTY_CENTER)
  const [overheadForm, setOverheadForm] = useState({ year: '1404', month: '1', amount: '' })
  const [wipForm, setWipForm] = useState({
    year: '1404', month: '1', completed_units: '', ending_wip_units: '', percent_complete: '', notes: '',
  })

  const load = useCallback(async () => {
    try {
      let data = { results: [] }
      if (activeTab === 'cost-centers') data = await api.costCenters()
      else if (activeTab === 'overhead') data = await api.overheadPeriods()
      else if (activeTab === 'wip-close') data = await api.wipCloses()
      else if (activeTab === 'spoilage') data = await api.spoilage()
      setRows(data.results || [])
      setError('')
    } catch (err) {
      setError(err.message || 'خطا در بارگذاری')
    } finally {
      setLoading(false)
    }
  }, [activeTab, api])

  useEffect(() => {
    const timer = setTimeout(() => { load() }, 0)
    return () => clearTimeout(timer)
  }, [load])

  const saveCenter = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await api.saveCostCenter({
        ...centerForm,
        base_quantity: Number(centerForm.base_quantity) || 0,
      })
      setCenterForm(EMPTY_CENTER)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveOverhead = async (event) => {
    event.preventDefault()
    try {
      await api.saveOverhead({
        year: Number(overheadForm.year),
        month: Number(overheadForm.month),
        amount: Number(overheadForm.amount) || 0,
      })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const allocate = async (id) => {
    setError('')
    try {
      await api.allocateOverhead(id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveWip = async (event) => {
    event.preventDefault()
    try {
      await api.saveWipClose({
        year: Number(wipForm.year),
        month: Number(wipForm.month),
        completed_units: Number(wipForm.completed_units) || 0,
        ending_wip_units: Number(wipForm.ending_wip_units) || 0,
        percent_complete: Number(wipForm.percent_complete) || 0,
        notes: wipForm.notes,
      })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className={fromLegacy('accounting-doc-list-toolbar')}>
        {COST_TABS.map((tab) => (
          <Button
            key={tab.id}
            type="button"
            variant={tab.id === activeTab ? 'primary' : 'ghost'}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </Button>
        ))}
      </div>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {loading && <div className={fromLegacy('loading')}>در حال بارگذاری…</div>}

      {activeTab === 'cost-centers' && (
        <Card title="مراکز هزینه">
          {canCreate && (
            <form onSubmit={saveCenter} className={fromLegacy('form form-grid-2')}>
              <Field label="کد"><input value={centerForm.code} onChange={(e) => setCenterForm({ ...centerForm, code: e.target.value })} required /></Field>
              <Field label="نام"><input value={centerForm.name} onChange={(e) => setCenterForm({ ...centerForm, name: e.target.value })} required /></Field>
              <Field label="نوع">
                <select value={centerForm.kind} onChange={(e) => setCenterForm({ ...centerForm, kind: e.target.value })}>
                  <option value="production">تولید</option>
                  <option value="showroom">شوروم</option>
                  <option value="admin">اداری</option>
                </select>
              </Field>
              <Field label="مبنای تسهیم">
                <select value={centerForm.allocation_base} onChange={(e) => setCenterForm({ ...centerForm, allocation_base: e.target.value })}>
                  <option value="machine_hours">ساعات ماشین</option>
                  <option value="floor_area">متراژ</option>
                  <option value="labor_hours">ساعات کار</option>
                  <option value="direct_cost">بهای مستقیم</option>
                </select>
              </Field>
              <Field label="مقدار مبنا"><input className={fromLegacy('ltr')} type="number" min="0" step="0.001" value={centerForm.base_quantity} onChange={(e) => setCenterForm({ ...centerForm, base_quantity: e.target.value })} /></Field>
              <Field label="کد شعبه"><input value={centerForm.branch} onChange={(e) => setCenterForm({ ...centerForm, branch: e.target.value })} placeholder="اختیاری" /></Field>
              <Button type="submit">ثبت مرکز</Button>
            </form>
          )}
          {!rows.length ? <EmptyState text="مرکز هزینه‌ای ثبت نشده است." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>کد</th><th>نام</th><th>نوع</th><th>مبنا</th><th>مقدار</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.code}</td>
                    <td>{row.name}</td>
                    <td>{row.kind_label}</td>
                    <td>{row.allocation_base_label}</td>
                    <td>{formatNumber(row.base_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {activeTab === 'overhead' && (
        <Card title="تسهیم سربار">
          {canCreate && (
            <form onSubmit={saveOverhead} className={fromLegacy('form form-grid-2')}>
              <Field label="سال"><input className={fromLegacy('ltr')} value={overheadForm.year} onChange={(e) => setOverheadForm({ ...overheadForm, year: e.target.value })} required /></Field>
              <Field label="ماه"><input className={fromLegacy('ltr')} value={overheadForm.month} onChange={(e) => setOverheadForm({ ...overheadForm, month: e.target.value })} required /></Field>
              <Field label="مبلغ استخر"><input className={fromLegacy('ltr')} type="number" min="1" value={overheadForm.amount} onChange={(e) => setOverheadForm({ ...overheadForm, amount: e.target.value })} required /></Field>
              <Button type="submit">ذخیره دوره</Button>
            </form>
          )}
          {!rows.length ? <EmptyState text="دوره‌ای ثبت نشده است." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>دوره</th><th>مبلغ</th><th>وضعیت</th><th>سند</th><th></th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.year}/{row.month}</td>
                    <td>{formatNumber(row.amount)}</td>
                    <td>{row.status_label}</td>
                    <td>{row.document_code || '—'}</td>
                    <td>{canCreate && row.journal_status !== 'posted' && (
                      <button type="button" className={fromLegacy('link')} onClick={() => allocate(row.id)}>تسهیم</button>
                    )}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {activeTab === 'wip-close' && (
        <Card title="آحاد معادل">
          {canCreate && (
            <form onSubmit={saveWip} className={fromLegacy('form form-grid-2')}>
              <Field label="سال"><input className={fromLegacy('ltr')} value={wipForm.year} onChange={(e) => setWipForm({ ...wipForm, year: e.target.value })} required /></Field>
              <Field label="ماه"><input className={fromLegacy('ltr')} value={wipForm.month} onChange={(e) => setWipForm({ ...wipForm, month: e.target.value })} required /></Field>
              <Field label="تکمیل‌شده"><input className={fromLegacy('ltr')} type="number" min="0" step="0.001" value={wipForm.completed_units} onChange={(e) => setWipForm({ ...wipForm, completed_units: e.target.value })} /></Field>
              <Field label="نیمه‌کاره"><input className={fromLegacy('ltr')} type="number" min="0" step="0.001" value={wipForm.ending_wip_units} onChange={(e) => setWipForm({ ...wipForm, ending_wip_units: e.target.value })} /></Field>
              <Field label="درصد تکمیل"><input className={fromLegacy('ltr')} type="number" min="0" max="100" step="0.01" value={wipForm.percent_complete} onChange={(e) => setWipForm({ ...wipForm, percent_complete: e.target.value })} /></Field>
              <Field label="یادداشت"><input value={wipForm.notes} onChange={(e) => setWipForm({ ...wipForm, notes: e.target.value })} /></Field>
              <Button type="submit">ثبت بستن</Button>
            </form>
          )}
          {!rows.length ? <EmptyState text="بستن دوره‌ای ثبت نشده است." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>دوره</th><th>تکمیل‌شده</th><th>نیمه‌کاره</th><th>درصد</th><th>آحاد معادل</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.year}/{row.month}</td>
                    <td>{formatNumber(row.completed_units)}</td>
                    <td>{formatNumber(row.ending_wip_units)}</td>
                    <td>{formatNumber(row.percent_complete)}</td>
                    <td>{formatNumber(row.equivalent_units)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {activeTab === 'spoilage' && (
        <Card title="مقایسه ضایعات">
          {!rows.length ? <EmptyState text="مصرفی برای مقایسه یافت نشد." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>متریال</th><th>واقعی</th><th>استاندارد</th><th>مجاز</th><th>وضعیت</th></tr></thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.material_id}-${index}`}>
                    <td>{row.material_name}</td>
                    <td>{formatNumber(row.actual_quantity)}</td>
                    <td>{formatNumber(row.standard_quantity)}</td>
                    <td>{formatNumber(row.allowed_quantity)}</td>
                    <td>{row.abnormal ? 'خارج از نرخ' : 'در محدوده'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
