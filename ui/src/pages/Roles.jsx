// مدیریت نقش‌ها و مجوزها — فقط مدیر سیستم

import { useCallback, useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'

const EMPTY_ROLE = {
  label: '',
  slug: '',
  description: '',
  needs_branch: false,
  color: '#6366f1',
  permissions: [],
}

export default function Roles() {
  const [matrix, setMatrix] = useState({ permissions: [], roles: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState(EMPTY_ROLE)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await authApi.permissionMatrix()
      setMatrix(data)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openEdit = (role) => {
    setSelected(role)
    setForm({
      label: role.label,
      slug: role.slug,
      description: role.description || '',
      needs_branch: role.needs_branch,
      color: role.color || '#6366f1',
      permissions: [...(role.permissions || [])],
    })
    setModalOpen(true)
  }

  const openCreate = () => {
    setSelected(null)
    setForm(EMPTY_ROLE)
    setModalOpen(true)
  }

  const togglePerm = (code) => {
    setForm((f) => ({
      ...f,
      permissions: f.permissions.includes(code)
        ? f.permissions.filter((p) => p !== code)
        : [...f.permissions, code],
    }))
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (selected) {
        await authApi.updateRoleDefinition(selected.slug, form)
        setInfo('نقش به‌روز شد.')
      } else {
        await authApi.createRoleDefinition(form)
        setInfo('نقش جدید ساخته شد.')
      }
      setModalOpen(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeRole = async (role) => {
    if (role.is_builtin) return
    if (!window.confirm(`نقش «${role.label}» حذف شود؟`)) return
    try {
      await authApi.deleteRoleDefinition(role.slug)
      setInfo('نقش حذف شد.')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const permOptions = selected?.slug === 'admin'
    ? matrix.permissions
    : (matrix.assignable_permissions?.length ? matrix.assignable_permissions : matrix.permissions)

  const isAdminRole = selected?.slug === 'admin' || form.slug === 'admin'

  if (loading) return <div className="page"><p className="muted">در حال بارگذاری…</p></div>

  return (
    <div className="page roles-page">
      {error && <div className="alert-error">{error}</div>}
      {info && <div className="alert-info">{info}</div>}

      <Card title="نقش‌ها و دسترسی‌ها" actions={<Button onClick={openCreate}>+ نقش سفارشی</Button>}>
        <p className="muted" style={{ marginBottom: 16 }}>
          فقط مدیر سیستم می‌تواند نقش بسازد. تنها نقش پیش‌فرض «مدیر سیستم» است؛ بقیه را خودتان تعریف کنید.
        </p>

        {matrix.roles.length === 0 ? (
          <EmptyState message="نقشی تعریف نشده" />
        ) : (
          <div className="roles-grid">
            {matrix.roles.map((role) => (
              <div key={role.slug} className="role-card" style={{ borderColor: role.color }}>
                <div className="role-card-head">
                  <Badge color={role.color}>{role.label}</Badge>
                  {role.is_builtin && <span className="muted small">پیش‌فرض</span>}
                </div>
                <p className="muted small">{role.description || role.slug}</p>
                <p className="muted small">{role.permissions?.length || 0} مجوز</p>
                <div className="role-card-actions">
                  {role.slug !== 'admin' && (
                    <button type="button" className="link" onClick={() => openEdit(role)}>ویرایش مجوزها</button>
                  )}
                  {role.slug === 'admin' && (
                    <span className="muted small">همه مجوزها — غیرقابل ویرایش</span>
                  )}
                  {!role.is_builtin && (
                    <button type="button" className="link danger" onClick={() => removeRole(role)}>حذف</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={selected ? `ویرایش ${selected.label}` : 'نقش جدید'}>
        <form onSubmit={save} className="form-grid">
          <Field label="عنوان نقش">
            <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} required />
          </Field>
          {!selected && (
            <Field label="شناسه (انگلیسی)">
              <input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="branch_supervisor" />
            </Field>
          )}
          <Field label="توضیح">
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="رنگ">
            <input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
          </Field>
          <label className="checkbox-row">
            <input type="checkbox" checked={form.needs_branch} onChange={(e) => setForm({ ...form, needs_branch: e.target.checked })} />
            نیاز به انتخاب شعبه
          </label>

          <div className="perm-matrix">
            <h4>مجوزها</h4>
            {isAdminRole && (
              <p className="muted small">نقش مدیر سیستم همیشه همه مجوزها را دارد.</p>
            )}
            <div className="perm-grid">
              {permOptions.map((p) => (
                <label key={p.code} className="perm-item">
                  <input
                    type="checkbox"
                    checked={isAdminRole || form.permissions.includes(p.code)}
                    disabled={isAdminRole}
                    onChange={() => togglePerm(p.code)}
                  />
                  <span>{p.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="form-actions">
            <Button type="submit" disabled={saving}>{saving ? '…' : 'ذخیره'}</Button>
            <Button type="button" variant="ghost" onClick={() => setModalOpen(false)}>انصراف</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
