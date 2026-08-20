// حضور و غیاب — فقط مدیر سیستم

import { useEffect, useState } from 'react'
import { attendanceApi, staffApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { useConfirm } from '../context/ConfirmContext'
import { useConfig } from '../context/ConfigContext'
import { formatDate } from '../utils/format'
import { todayIso } from '../utils/jalali'

const EMPTY = { seller_id: '', date: todayIso(), status: 'present', notes: '', work_branch: '' }

export default function Attendance() {
  const confirm = useConfirm()
  const { branchOptions } = useConfig()
  const [records, setRecords] = useState([])
  const [sellers, setSellers] = useState([])
  const [branch, setBranch] = useState('')
  const [selectedSellerId, setSelectedSellerId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [filterDate, setFilterDate] = useState('')

  const branchLabel = branchOptions.find((b) => b.value === branch)?.label

  useEffect(() => {
    if (!branch && branchOptions.length) setBranch(branchOptions[0].value)
  }, [branch, branchOptions])

  const loadSellers = async () => {
    const data = await staffApi.list(branch)
    setSellers(data.results)
  }

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ branch })
      if (filterDate) {
        params.set('date_from', filterDate)
        params.set('date_to', filterDate)
      }
      const data = await attendanceApi.list(params.toString())
      setRecords(data.results)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSellers().catch((e) => setError(e.message)) }, [branch])
  useEffect(() => { load() }, [branch, filterDate])

  const openCreateForSeller = (sellerId) => {
    setEditing(null)
    setForm({ ...EMPTY, seller_id: String(sellerId), work_branch: branch })
    setModalOpen(true)
  }

  const save = async (e) => {
    e.preventDefault()
    try {
      const payload = { ...form, branch, work_branch: form.work_branch || branch }
      if (editing) await attendanceApi.update(editing.id, payload)
      else await attendanceApi.create(payload)
      setModalOpen(false)
      setForm(EMPTY)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!await confirm({
      title: 'حذف رکورد',
      message: 'حذف این رکورد؟',
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    await attendanceApi.remove(id)
    load()
  }

  return (
    <div className="page">
      <Card title="حضور و غیاب (مدیر)" actions={
        <Button onClick={() => openCreateForSeller(selectedSellerId)} disabled={!selectedSellerId}>+ ثبت</Button>
      }>
        {error && <div className="alert-error">{error}</div>}
        <div className="branch-tabs">
          {branchOptions.map((b) => (
            <button key={b.value} type="button" className={`branch-tab ${branch === b.value ? 'active' : ''}`} onClick={() => setBranch(b.value)}>
              {b.label}
            </button>
          ))}
        </div>
        <Field label={`فروشندگان ${branchLabel}`}>
          <div className="seller-grid">
            {sellers.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`seller-card ${selectedSellerId === String(s.id) ? 'selected' : ''}`}
                onClick={() => setSelectedSellerId(String(s.id))}
              >
                <span className="seller-name">{s.full_name}</span>
              </button>
            ))}
          </div>
        </Field>
        <FilterBar>
          <Field label="فیلتر تاریخ">
            <PersianDateInput
              value={filterDate}
              onChange={setFilterDate}
              placeholder="همه تاریخ‌ها"
              onClear={() => setFilterDate('')}
              clearLabel="همه تاریخ‌ها"
            />
          </Field>
        </FilterBar>
        {loading ? <div className="loading">…</div> : (
          <table className="table">
            <thead>
              <tr><th>فروشنده</th><th>شعبه کاری</th><th>تاریخ</th><th>وضعیت</th><th>تایید</th><th>عملیات</th></tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>{r.seller_name}</td>
                  <td>{r.work_branch_label}</td>
                  <td>{formatDate(r.date)}</td>
                  <td><Badge color={r.status === 'present' ? 'var(--success)' : 'var(--danger)'}>{r.status_display}</Badge></td>
                  <td><Badge color={r.approval_status === 'approved' ? 'var(--success)' : 'var(--warning)'}>{r.approval_status_display}</Badge></td>
                  <td className="row-actions">
                    <button type="button" className="link danger" onClick={() => remove(r.id)}>حذف</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Modal title="ثبت حضور" open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className="form">
          <Field label="فروشنده">
            <Select
              value={form.seller_id}
              onChange={(v) => setForm({ ...form, seller_id: v })}
              options={sellers.map((s) => ({ value: String(s.id), label: s.full_name }))}
              placeholder="—"
              required
            />
          </Field>
          <Field label="شعبه کاری">
            <Select
              value={form.work_branch || branch}
              onChange={(v) => setForm({ ...form, work_branch: v })}
              options={branchOptions}
            />
          </Field>
          <Field label="تاریخ"><PersianDateInput value={form.date} onChange={(v) => setForm({ ...form, date: v })} required /></Field>
          <Field label="وضعیت">
            <Select
              value={form.status}
              onChange={(v) => setForm({ ...form, status: v })}
              options={[
                { value: 'present', label: 'حاضر' },
                { value: 'absent', label: 'غایب' },
              ]}
            />
          </Field>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>
    </div>
  )
}
