import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '../ui'
import { fromLegacy } from '../../styles/tw'

const emptyForm = {
  event_key: '',
  role: '',
  side: 'debit',
  account_id: '',
  effective_from: new Date().toISOString().slice(0, 10),
  effective_to: '',
  item_category: '',
  priority: 0,
  is_active: true,
}

export default function AccountMappingsPanel({ api, accounts }) {
  const [rows, setRows] = useState([])
  const [coverage, setCoverage] = useState({ results: [], missing: 0 })
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const [mappingPayload, coveragePayload] = await Promise.all([
      api.accountMappings(),
      api.mappingCoverage(),
    ])
    setRows(mappingPayload.results || [])
    setCoverage(coveragePayload || { results: [], missing: 0 })
  }, [api])

  useEffect(() => {
    load().catch((error) => console.error('خطا در بارگذاری اتصال حساب‌ها:', error))
  }, [load])

  const ruleOptions = useMemo(() => {
    const seen = new Set()
    return (coverage.results || []).filter((item) => {
      const key = `${item.event_key}|${item.role}|${item.side}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [coverage])

  const selectRule = (value) => {
    const selected = ruleOptions.find((item) => `${item.event_key}|${item.role}|${item.side}` === value)
    if (selected) setForm((current) => ({ ...current, ...selected, account_id: current.account_id }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      const payload = { ...form, account_id: Number(form.account_id), priority: Number(form.priority || 0) }
      if (editingId) await api.updateAccountMapping(editingId, payload)
      else await api.createAccountMapping(payload)
      setEditingId(null)
      setForm(emptyForm)
      await load()
    } catch (error) {
      alert(error.message || 'ذخیره اتصال حساب ممکن نشد.')
    } finally {
      setBusy(false)
    }
  }

  const edit = (row) => {
    setEditingId(row.id)
    setForm({
      event_key: row.event_key,
      role: row.role,
      side: row.side,
      account_id: String(row.account_id),
      effective_from: row.effective_from,
      effective_to: row.effective_to || '',
      item_category: row.item_category || '',
      priority: row.priority,
      is_active: row.is_active,
    })
  }

  const remove = async (row) => {
    if (!window.confirm(`اتصال «${row.event_key} / ${row.role}» حذف شود؟`)) return
    try {
      await api.deleteAccountMapping(row.id)
      await load()
    } catch (error) {
      alert(error.message || 'حذف اتصال ممکن نشد.')
    }
  }

  return (
    <section className={fromLegacy('card mt-6')} dir="rtl">
      <div className={fromLegacy('flex items-center justify-between gap-3 mb-4')}>
        <div>
          <h2 className={fromLegacy('text-lg font-bold')}>اتصال حساب‌ها</h2>
          <p className={fromLegacy('text-sm text-muted')}>
            حساب قابل ثبت هر نقش را تعیین کنید. {coverage.missing || 0} نقش بدون پوشش است.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className={fromLegacy('grid grid-cols-1 md:grid-cols-4 gap-3 mb-5')}>
        <select
          value={form.event_key ? `${form.event_key}|${form.role}|${form.side}` : ''}
          onChange={(event) => selectRule(event.target.value)}
          required
        >
          <option value="">انتخاب قانون و نقش…</option>
          {ruleOptions.map((item) => (
            <option key={`${item.event_key}|${item.role}|${item.side}`} value={`${item.event_key}|${item.role}|${item.side}`}>
              {item.event_key} — {item.role} ({item.side === 'debit' ? 'بدهکار' : 'بستانکار'})
            </option>
          ))}
        </select>
        <input value={form.event_key} onChange={(event) => setForm({ ...form, event_key: event.target.value })} placeholder="کلید قانون" required />
        <input value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} placeholder="نقش حساب" required />
        <select value={form.side} onChange={(event) => setForm({ ...form, side: event.target.value })}>
          <option value="debit">بدهکار</option>
          <option value="credit">بستانکار</option>
        </select>
        <select value={form.account_id} onChange={(event) => setForm({ ...form, account_id: event.target.value })} required>
          <option value="">حساب مقصد…</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>{account.code} — {account.name}</option>
          ))}
        </select>
        <input type="date" value={form.effective_from} onChange={(event) => setForm({ ...form, effective_from: event.target.value })} required />
        <input type="date" value={form.effective_to || ''} onChange={(event) => setForm({ ...form, effective_to: event.target.value })} title="پایان اعتبار (اختیاری)" />
        <input value={form.item_category || ''} onChange={(event) => setForm({ ...form, item_category: event.target.value })} placeholder="دسته کالا (اختیاری)" />
        <input type="number" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })} placeholder="اولویت" />
        <label className={fromLegacy('flex items-center gap-2')}>
          <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
          فعال
        </label>
        <Button type="submit" variant="primary" disabled={busy}>{editingId ? 'ذخیره ویرایش' : 'افزودن اتصال'}</Button>
      </form>

      <div className={fromLegacy('overflow-x-auto')}>
        <table className={fromLegacy('data-table w-full')}>
          <thead><tr><th>قانون</th><th>نقش</th><th>سمت</th><th>حساب</th><th>اولویت</th><th>عملیات</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.event_key}</td>
                <td>{row.role}</td>
                <td>{row.side === 'debit' ? 'بدهکار' : 'بستانکار'}</td>
                <td>{row.account.code} — {row.account.name}</td>
                <td>{row.priority.toLocaleString('fa-IR')}</td>
                <td>
                  <Button type="button" variant="ghost" onClick={() => edit(row)}>ویرایش</Button>
                  <Button type="button" variant="danger" onClick={() => remove(row)}>حذف</Button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="6">هنوز اتصالی ثبت نشده است؛ رفتار قدیمی همچنان استفاده می‌شود.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}
