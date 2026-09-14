// حضور و غیاب — فقط مدیر سیستم

import { useEffect, useState } from 'react'
import { attendanceApi, staffApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE, PICKER_LIMIT } from '../config/pagination'
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
  const [loadingMore, setLoadingMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [filterDate, setFilterDate] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [approvalFilter, setApprovalFilter] = useState('')

  const branchLabel = branchOptions.find((b) => b.value === branch)?.label

  useEffect(() => {
    if (!branch && branchOptions.length) setBranch(branchOptions[0].value)
  }, [branch, branchOptions])

  const loadSellers = async () => {
    const data = await staffApi.list(branch, 'seller', { limit: PICKER_LIMIT })
    setSellers(data.results)
  }

  const load = async ({ append = false, offset: nextOffset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const params = new URLSearchParams({ branch })
      if (filterDate) {
        params.set('date_from', filterDate)
        params.set('date_to', filterDate)
      }
      if (statusFilter) params.set('status', statusFilter)
      if (approvalFilter) params.set('approval_status', approvalFilter)
      params.set('offset', String(nextOffset))
      params.set('limit', String(PAGE_SIZE))
      const data = await attendanceApi.list(params.toString())
      setRecords((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))
      setTotal(data.total || 0)
      setOffset(data.offset ?? nextOffset)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => { loadSellers().catch((e) => setError(e.message)) }, [branch])
  useEffect(() => { load() }, [branch, filterDate, statusFilter, approvalFilter])

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
          <Field label="وضعیت حضور">
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: '', label: 'همه' },
                { value: 'present', label: 'حاضر' },
                { value: 'absent', label: 'غایب' },
              ]}
              placeholder="همه"
            />
          </Field>
          <Field label="تایید">
            <Select
              value={approvalFilter}
              onChange={setApprovalFilter}
              options={[
                { value: '', label: 'همه' },
                { value: 'pending', label: 'در انتظار' },
                { value: 'approved', label: 'تایید شده' },
                { value: 'rejected', label: 'رد شده' },
              ]}
              placeholder="همه"
            />
          </Field>
        </FilterBar>
        {loading ? <div className="loading">…</div> : records.length === 0 ? (
          <EmptyState text="رکوردی یافت نشد." />
        ) : (
          <>
            <div className="table-wrap attendance-table-desktop">
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
            </div>
            <div className="attendance-cards-mobile">
              {records.map((r) => (
                <div key={r.id} className="m-card">
                  <div className="m-card-head">
                    <strong>{r.seller_name}</strong>
                    <span className="muted">{formatDate(r.date)}</span>
                  </div>
                  <div className="m-card-grid">
                    <div><span className="muted">شعبه کاری</span>{r.work_branch_label}</div>
                    <div><span className="muted">وضعیت</span><Badge color={r.status === 'present' ? 'var(--success)' : 'var(--danger)'}>{r.status_display}</Badge></div>
                    <div><span className="muted">تایید</span><Badge color={r.approval_status === 'approved' ? 'var(--success)' : 'var(--warning)'}>{r.approval_status_display}</Badge></div>
                  </div>
                  <div className="m-card-actions">
                    <button type="button" className="link danger" onClick={() => remove(r.id)}>حذف</button>
                  </div>
                </div>
              ))}
            </div>
            <LoadMoreButton
              hasMore={records.length < total}
              loading={loadingMore}
              onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
            />
          </>
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
