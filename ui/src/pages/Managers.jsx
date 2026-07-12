// فهرست مدیران — جدا از فروشندگان

import { useEffect, useState } from 'react'
import { staffApi } from '../api/client'
import { Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useConfig } from '../context/ConfigContext'
import { hasPermission } from '../utils/permissions'

const EMPTY = { full_name: '', phone: '' }

export default function Managers() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const { branchOptions } = useConfig()
  const canView = hasPermission(user, 'view_managers') || hasPermission(user, 'manage_managers')
  const canManage = hasPermission(user, 'manage_managers')
  const canDelete = hasPermission(user, 'delete_managers')
  const [managers, setManagers] = useState([])
  const [branch, setBranch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)

  const load = async () => {
    setLoading(true)
    try {
      const data = await staffApi.list(branch, 'manager')
      setManagers(data.results)
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
      await staffApi.create({ ...form, branch, staff_kind: 'manager' })
      setModalOpen(false)
      setForm(EMPTY)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (manager) => {
    const msg = manager.has_login
      ? `«${manager.full_name}» حذف شود؟ این فرد حساب ورود هم دارد؛ فقط از فهرست مدیران حذف می‌شود.`
      : `«${manager.full_name}» از فهرست مدیران حذف شود؟`
    if (!await confirm({
      title: 'حذف مدیر',
      message: msg,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await staffApi.remove(manager.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const branchLabel = branchOptions.find((b) => b.value === branch)?.label

  if (!canView) {
    return (
      <div className="page">
        <Card title="مدیران">
          <div className="alert-error">دسترسی مشاهده مدیران را ندارید.</div>
        </Card>
      </div>
    )
  }

  return (
    <div className="page">
      <Card
        title="مدیران"
        actions={canManage ? <Button onClick={() => { setForm(EMPTY); setModalOpen(true) }}>+ مدیر</Button> : null}
      >
        {error && <div className="alert-error">{error}</div>}
        <p className="muted" style={{ marginBottom: 12 }}>
          مدیران در فهرست فروشندگان نمایش داده نمی‌شوند.
        </p>
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
        {loading ? <div className="loading">در حال بارگذاری…</div> : managers.length === 0 ? (
          <EmptyState text={`مدیری در ${branchLabel} ثبت نشده.`} />
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
              {managers.map((m) => (
                <tr key={m.id}>
                  <td>{m.full_name}</td>
                  <td className="ltr">{m.phone || '—'}</td>
                  <td>{m.branch_label}</td>
                  {canDelete && (
                    <td>
                      <button type="button" className="link danger" onClick={() => remove(m)}>
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
      <Modal title={`افزودن مدیر — ${branchLabel}`} open={modalOpen} onClose={() => setModalOpen(false)}>
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
