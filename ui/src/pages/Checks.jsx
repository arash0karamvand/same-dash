// مدیریت چک — CRUD + گزارش ماهانه + خروجی فرم اکسل

import { useEffect, useState } from 'react'
import { installmentsApi, salesApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import OfficeSectionCard from '../components/OfficeSectionCard'
import { CHECK_NOTES_LABEL, CHECK_ROW_FIELDS, EMPTY_CHECK_ROW } from '../config/checkForm'
import { OFFICE_INSTALLMENTS_FILTER } from '../config/recordFilterSections'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate, formatMoney } from '../utils/format'
import { currentJalali, jalaliMonthToGregorian, PERSIAN_MONTHS, todayIso, toPersianDigits } from '../utils/jalali'

const EMPTY = {
  sale_id: '',
  payment_method: 'check',
  ...EMPTY_CHECK_ROW,
  received_at: todayIso(),
  due_date: todayIso(),
}

function CheckFormFields({ form, setForm, editingCustomer = '' }) {
  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }))

  return (
    <>
      {editingCustomer && <p className="muted">نام مشتری: {editingCustomer}</p>}
      {CHECK_ROW_FIELDS.map((field) => {
        if (field.type === 'date') {
          return (
            <Field key={field.key} label={field.label}>
              <PersianDateInput
                value={form[field.key] || todayIso()}
                onChange={(v) => set(field.key, v)}
                required={field.key === 'due_date'}
              />
            </Field>
          )
        }
        if (field.type === 'money') {
          return (
            <Field key={field.key} label={field.label}>
              <MoneyInput
                min="1"
                value={form.amount}
                onChange={(e) => set('amount', e.target.value)}
                required
              />
            </Field>
          )
        }
        return (
          <Field key={field.key} label={field.label}>
            <input
              className={field.ltr ? 'ltr' : undefined}
              value={form[field.key] || ''}
              onChange={(e) => set(field.key, e.target.value)}
              required={field.key === 'check_number'}
            />
          </Field>
        )
      })}
      <Field label={CHECK_NOTES_LABEL}>
        <input value={form.notes || ''} onChange={(e) => set('notes', e.target.value)} placeholder="توضیح اختیاری…" />
      </Field>
    </>
  )
}

export default function Checks() {
  const confirm = useConfirm()
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
      setError('چک پرداخت‌شده قابل ویرایش نیست.')
      return
    }
    setEditing(item)
    setForm({
      sale_id: String(item.sale_id),
      payment_method: 'check',
      amount: String(item.amount),
      due_date: item.due_date?.slice(0, 10) || todayIso(),
      check_number: item.check_number || '',
      bank_name: item.bank_name || '',
      notes: item.notes || '',
      received_at: item.received_at?.slice(0, 10) || todayIso(),
      receiver_name: item.receiver_name || '',
    })
    setModalOpen(true)
  }

  const save = async (e) => {
    e.preventDefault()
    try {
      const payload = {
        sale_id: form.sale_id,
        payment_method: 'check',
        amount: Number(form.amount),
        due_date: form.due_date,
        check_number: form.check_number,
        bank_name: form.bank_name,
        received_at: form.received_at || null,
        receiver_name: form.receiver_name || '',
        notes: form.notes || '',
      }
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

  const exportExcel = async () => {
    try {
      const params = new URLSearchParams({
        date_from: range.dateFrom,
        date_to: range.dateTo,
        payment_method: 'check',
      })
      await installmentsApi.exportExcel(params.toString())
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!await confirm({
      title: 'حذف چک',
      message: 'این چک حذف شود؟',
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
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
      <OfficeSectionCard
        section={OFFICE_INSTALLMENTS_FILTER}
        actions={
          <>
            <Button variant="ghost" onClick={exportExcel}>دانلود اکسل فرم چک</Button>
            <Button onClick={openCreate}>+ افزودن چک</Button>
          </>
        }
      >
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
          <EmptyState text="چکی در این ماه نیست." />
        ) : (
          <>
            <div className="table-wrap checks-table-desktop">
              <table className="table">
                <thead>
                  <tr>
                    <th>مشتری</th>
                    <th>تحویل به شعبه</th>
                    <th>بانک</th>
                    <th>سررسید</th>
                    <th>شماره چک</th>
                    <th>مبلغ</th>
                    <th>تحویل‌گیرنده</th>
                    <th>وضعیت</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.customer_name}</td>
                      <td>{i.received_at ? formatDate(i.received_at) : '—'}</td>
                      <td>{i.bank_name || '—'}</td>
                      <td>{formatDate(i.due_date)}</td>
                      <td className="ltr">{i.check_number || '—'}</td>
                      <td>{formatMoney(i.amount)}</td>
                      <td>{i.receiver_name || '—'}</td>
                      <td><Badge color={i.status === 'paid' ? '#10b981' : '#f59e0b'}>{i.status_display}</Badge></td>
                      <td className="row-actions">
                        {i.status !== 'paid' && (
                          <>
                            <button type="button" className="link" onClick={() => openEdit(i)}>ویرایش</button>
                            <button type="button" className="link" onClick={() => pay(i.id)}>وصول</button>
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
                    <div><span className="muted">تحویل به شعبه</span>{i.received_at ? formatDate(i.received_at) : '—'}</div>
                    <div><span className="muted">بانک</span>{i.bank_name || '—'}</div>
                    <div><span className="muted">سررسید</span>{formatDate(i.due_date)}</div>
                    <div><span className="muted">شماره چک</span><span className="ltr">{i.check_number || '—'}</span></div>
                    <div><span className="muted">مبلغ</span><strong>{formatMoney(i.amount)}</strong></div>
                    <div><span className="muted">تحویل‌گیرنده</span>{i.receiver_name || '—'}</div>
                  </div>
                  <div className="m-card-actions">
                    {i.status !== 'paid' && (
                      <>
                        <button type="button" className="link" onClick={() => openEdit(i)}>ویرایش</button>
                        <button type="button" className="link" onClick={() => pay(i.id)}>وصول</button>
                      </>
                    )}
                    <button type="button" className="link danger" onClick={() => remove(i.id)}>حذف</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </OfficeSectionCard>
      <Modal title={editing ? 'ویرایش چک' : 'ثبت چک'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null) }}>
        <form onSubmit={save} className="form">
          {!editing && (
            <Field label="فروش (نام مشتری از فاکتور)">
              <Select
                value={form.sale_id}
                onChange={(v) => setForm({ ...form, sale_id: v })}
                options={sales.map((s) => ({ value: String(s.id), label: `${s.customer_name} — ${s.invoice_number || s.id}` }))}
                placeholder="— انتخاب —"
                required
              />
            </Field>
          )}
          <CheckFormFields form={form} setForm={setForm} editingCustomer={editing?.customer_name} />
          <Button type="submit">{editing ? 'ذخیره' : 'ثبت چک'}</Button>
        </form>
      </Modal>
    </div>
  )
}
