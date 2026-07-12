// فهرست فروشندگان — مدیر، مدیر فروش، حسابدار

import { useEffect, useState } from 'react'
import { staffApi } from '../api/client'
import { Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useConfig } from '../context/ConfigContext'
import { hasPermission } from '../utils/permissions'

const EMPTY = { full_name: '', phone: '' }

export default function Sellers() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const { branchOptions } = useConfig()
  const canView = hasPermission(user, 'view_sellers')
    || hasPermission(user, 'manage_staff')
    || hasPermission(user, 'view_attendance')
  const canManage = hasPermission(user, 'manage_staff')
  const canDelete = hasPermission(user, 'delete_staff')
  const [sellers, setSellers] = useState([])
  const [branch, setBranch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)

  const load = async () => {
    setLoading(true)
    try {
      const data = await staffApi.list(branch)
      setSellers(data.results)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!branch && branchOptions.length) setBranch(branchOptions[0].value)
  }, [branch, branchOptions])

  useEffect(() => { if (branch) load() }, [branch])

  const save = async (e) => {
    e.preventDefault()
    try {
      await staffApi.create({ ...form, branch, staff_kind: 'seller' })
      setModalOpen(false)
      setForm(EMPTY)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (seller) => {
    const msg = seller.has_login
      ? `«${seller.full_name}» حذف شود؟ این فرد حساب ورود هم دارد؛ فقط از فهرست فروشندگان حذف می‌شود.`
      : `«${seller.full_name}» از فهرست فروشندگان حذف شود؟`
    if (!await confirm({
      title: 'حذف فروشنده',
      message: msg,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await staffApi.remove(seller.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const branchLabel = branchOptions.find((b) => b.value === branch)?.label

  if (!canView) {
    return (
      <div className="page">
        <Card title="فروشندگان">
          <div className="alert-error">دسترسی مشاهده فروشندگان را ندارید.</div>
        </Card>
      </div>
    )
  }

  return (
    <div className="page">
      <Card
        title="فروشندگان"
        actions={canManage ? <Button onClick={() => { setForm(EMPTY); setModalOpen(true) }}>+ فروشنده</Button> : null}
      >
        {error && <div className="alert-error">{error}</div>}
        <div className="branch-tabs">
          {branchOptions.map((b) => (
            <button
              key={b.value}
              type="button"
              className={`branch-tab ${branch === b.value ? 'active' : ''}`}
              onClick={() => setBranch(b.value)}
            >
              {b.label}
            </button>
          ))}
        </div>
        {loading ? <div className="loading">در حال بارگذاری…</div> : sellers.length === 0 ? (
          <EmptyState text={`فروشنده‌ای در ${branchLabel} ثبت نشده.`} />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>نام</th>
                <th>موبایل</th>
                <th>شعبه</th>
                {canDelete && <th>عملیات</th>}
              </tr>
            </thead>
            <tbody>
              {sellers.map((s) => (
                <tr key={s.id}>
                  <td>{s.full_name}</td>
                  <td className="ltr">{s.phone || '—'}</td>
                  <td>{s.branch_label}</td>
                  {canDelete && (
                    <td>
                      <button type="button" className="link danger" onClick={() => remove(s)}>
                        حذف
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Modal title={`افزودن فروشنده — ${branchLabel}`} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className="form">
          <Field label="نام کامل">
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          </Field>
          <Field label="موبایل (اختیاری)">
            <input className="ltr" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <p className="muted">بدون نام کاربری — فقط نام و شعبه ثبت می‌شود.</p>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>
    </div>
  )
}
