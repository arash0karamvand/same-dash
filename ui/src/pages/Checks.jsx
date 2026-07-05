// مدیریت اقساط و چک — CRUD + گزارش ماهانه

import { useEffect, useState } from 'react'
import { installmentsApi, salesApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { formatDate, formatMoney } from '../utils/format'
import { currentJalali, jalaliMonthToGregorian, PERSIAN_MONTHS, todayIso, toPersianDigits } from '../utils/jalali'

const EMPTY = {
  sale_id: '',
  amount: '',
  due_date: todayIso(),
  payment_method: 'check',
  check_number: '',
  bank_name: '',
  notes: '',
}

export default function Checks() {
  const init = currentJalali()
  const [items, setItems] = useState([])
  const [report, setReport] = useState(null)
  const [sales, setSales] = useState([])
  const [jYear, setJYear] = useState(init.year)
  const [jMonth, setJMonth] = useState(init.month)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)

  const range = jalaliMonthToGregorian(jYear, jMonth)
  const monthLabel = `${PERSIAN_MONTHS[jMonth - 1]} ${toPersianDigits(jYear)}`

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        date_from: range.dateFrom,
        date_to: range.dateTo,
        payment_method: 'check',
      })
      const [list, rep, salesData] = await Promise.all([
        installmentsApi.list(params.toString()),
        installmentsApi.checksReport({ dateFrom: range.dateFrom, dateTo: range.dateTo }),
        salesApi.list('payment_status=installment'),
      ])
      setItems(list.results)
      setReport(rep)
      setSales(salesData.results)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [jYear, jMonth])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY)
    setModalOpen(true)
  }

  const openEdit = (item) => {
    if (item.status === 'paid') {
      setError('قسط پرداخت‌شده قابل ویرایش نیست.')
      return
    }
    setEditing(item)
    setForm({
      sale_id: String(item.sale_id),
      amount: String(item.amount),
      due_date: item.due_date?.slice(0, 10) || todayIso(),
      payment_method: item.payment_method || 'check',
      check_number: item.check_number || '',
      bank_name: item.bank_name || '',
      notes: item.notes || '',
    })
    setModalOpen(true)
  }

  const save = async (e) => {
    e.preventDefault()
    try {
      const payload = { ...form, amount: Number(form.amount) }
      if (editing) {
        await installmentsApi.update(editing.id, payload)
      } else {
        await installmentsApi.create(payload)
      }
      setModalOpen(false)
      setForm(EMPTY)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const pay = async (id) => {
    try {
      await installmentsApi.pay(id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!confirm('حذف این قسط/چک؟')) return
    try {
      await installmentsApi.remove(id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page">
      {report && (
        <div className="stats-grid">
          <Card title={`چک‌های ${monthLabel}`}><p className="stat-value">{report.count} فقره</p></Card>
          <Card title="مجموع مبلغ"><p className="stat-value">{formatMoney(report.total_amount)}</p></Card>
          <Card title="پرداخت‌شده"><p className="stat-value">{formatMoney(report.paid_amount)}</p></Card>
          <Card title="مانده"><p className="stat-value">{formatMoney(report.pending_amount)}</p></Card>
        </div>
      )}
      <Card title="چک و اقساط" actions={<Button onClick={openCreate}>+ افزودن</Button>}>
        {error && <div className="alert-error">{error}</div>}
        <FilterBar>
          <Field label="ماه گزارش">
            <PersianMonthPicker
              year={jYear}
              month={jMonth}
              onChange={(y, m) => { setJYear(y); setJMonth(m) }}
            />
          </Field>
        </FilterBar>
        {loading ? <div className="loading">در حال بارگذاری…</div> : items.length === 0 ? (
          <EmptyState text="قسط/چکی در این ماه نیست." />
        ) : (
          <>
            <div className="table-wrap checks-table-desktop">
              <table className="table">
                <thead>
                  <tr><th>مشتری</th><th>مبلغ</th><th>سررسید</th><th>چک</th><th>بانک</th><th>وضعیت</th><th>عملیات</th></tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.customer_name}</td>
                      <td>{formatMoney(i.amount)}</td>
                      <td>{formatDate(i.due_date)}</td>
                      <td className="ltr">{i.check_number || '—'}</td>
                      <td>{i.bank_name || '—'}</td>
                      <td><Badge color={i.status === 'paid' ? '#10b981' : '#f59e0b'}>{i.status_display}</Badge></td>
                      <td className="row-actions">
                        {i.status !== 'paid' && (
                          <>
                            <button type="button" className="link" onClick={() => openEdit(i)}>ویرایش</button>
                            <button type="button" className="link" onClick={() => pay(i.id)}>پرداخت</button>
                          </>
                        )}
                        <button type="button" className="link danger" onClick={() => remove(i.id)}>حذف</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="checks-cards-mobile">
              {items.map((i) => (
                <div key={i.id} className="m-card">
                  <div className="m-card-head">
                    <strong>{i.customer_name}</strong>
                    <Badge color={i.status === 'paid' ? '#10b981' : '#f59e0b'}>{i.status_display}</Badge>
                  </div>
                  <div className="m-card-grid">
                    <div><span className="muted">مبلغ</span><strong>{formatMoney(i.amount)}</strong></div>
                    <div><span className="muted">سررسید</span>{formatDate(i.due_date)}</div>
                    <div><span className="muted">چک</span><span className="ltr">{i.check_number || '—'}</span></div>
                    <div><span className="muted">بانک</span>{i.bank_name || '—'}</div>
                  </div>
                  <div className="m-card-actions">
                    {i.status !== 'paid' && (
                      <>
                        <button type="button" className="link" onClick={() => openEdit(i)}>ویرایش</button>
                        <button type="button" className="link" onClick={() => pay(i.id)}>پرداخت</button>
                      </>
                    )}
                    <button type="button" className="link danger" onClick={() => remove(i.id)}>حذف</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
      <Modal title={editing ? 'ویرایش قسط/چک' : 'افزودن قسط/چک'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null) }}>
        <form onSubmit={save} className="form">
          {editing ? (
            <p className="muted">مشتری: {editing.customer_name}</p>
          ) : (
            <Field label="فروش">
              <Select
                value={form.sale_id}
                onChange={(v) => setForm({ ...form, sale_id: v })}
                options={sales.map((s) => ({ value: String(s.id), label: `${s.customer_name} — ${s.invoice_number || s.id}` }))}
                placeholder="— انتخاب —"
                required
              />
            </Field>
          )}
          <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>
          <Field label="تاریخ سررسید"><PersianDateInput value={form.due_date} onChange={(v) => setForm({ ...form, due_date: v })} required /></Field>
          <Field label="روش">
            <Select
              value={form.payment_method}
              onChange={(v) => setForm({ ...form, payment_method: v })}
              options={[
                { value: 'check', label: 'چک' },
                { value: 'cash', label: 'نقد' },
                { value: 'card', label: 'کارت' },
              ]}
            />
          </Field>
          <Field label="شماره چک"><input className="ltr" value={form.check_number} onChange={(e) => setForm({ ...form, check_number: e.target.value })} /></Field>
          <Field label="بانک"><input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} /></Field>
          <Field label="یادداشت"><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
          <Button type="submit">{editing ? 'ذخیره' : 'افزودن'}</Button>
        </form>
      </Modal>
    </div>
  )
}

