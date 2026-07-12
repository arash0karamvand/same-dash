// مدیریت نقش‌ها و مجوزها — فقط مدیر سیستم

import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/client'
import { useConfirm } from '../context/ConfirmContext'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { sectionHasMenuAccess, toggleSectionPermissions } from '../utils/permissions'

const LOCKED_ROLE_SLUGS = new Set(['admin', 'ceo'])

function isLockedRole(role) {
  return role?.is_locked || LOCKED_ROLE_SLUGS.has(role?.slug)
}

function isFullAccessRole(role, formSlug) {
  return role?.grants_full_access || formSlug === 'admin' || formSlug === 'ceo'
}

const EMPTY_ROLE = {
  label: '',
  slug: '',
  description: '',
  needs_branch: false,
  color: '#6366f1',
  permissions: [],
  parent_slug: '',
  sort_order: 50,
}

function buildRoleTree(roles) {
  const bySlug = new Map(roles.map((r) => [r.slug, { ...r, children: [] }]))
  const roots = []
  for (const role of bySlug.values()) {
    const parent = role.parent_slug && bySlug.get(role.parent_slug)
    if (parent) parent.children.push(role)
    else roots.push(role)
  }
  const sortNodes = (nodes) => {
    nodes.sort((a, b) => (a.sort_order ?? 50) - (b.sort_order ?? 50))
    nodes.forEach((n) => sortNodes(n.children))
  }
  sortNodes(roots)
  return roots
}

function RoleTreeCard({ role, depth, onEdit, onRemove, parentLabel }) {
  const locked = isLockedRole(role)
  return (
    <div className="role-hierarchy-item" style={{ '--role-depth': depth }}>
      <div className="role-card" style={{ borderColor: role.color }}>
        <div className="role-card-head">
          <Badge color={role.color}>{role.label}</Badge>
          {role.is_builtin && <span className="muted small">پیش‌فرض</span>}
        </div>
        <p className="muted small">{role.description || role.slug}</p>
        {parentLabel && (
          <p className="muted small role-parent-hint">زیرمجموعه: {parentLabel}</p>
        )}
        <p className="muted small">{role.permissions?.length || 0} مجوز</p>
        <div className="role-card-actions">
          {!locked ? (
            <button type="button" className="link" onClick={() => onEdit(role)}>ویرایش مجوزها</button>
          ) : (
            <span className="muted small">همه مجوزها — غیرقابل ویرایش</span>
          )}
          {role.slug !== 'admin' && (
            <button type="button" className="link danger" onClick={() => onRemove(role)}>حذف</button>
          )}
        </div>
      </div>
      {role.children?.length > 0 && (
        <div className="role-hierarchy-children">
          {role.children.map((child) => (
            <RoleTreeCard
              key={child.slug}
              role={child}
              depth={depth + 1}
              onEdit={onEdit}
              onRemove={onRemove}
              parentLabel={role.label}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Roles() {
  const confirm = useConfirm()
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

  const roleTree = useMemo(() => buildRoleTree(matrix.roles || []), [matrix.roles])

  const parentOptions = useMemo(
    () => (matrix.roles || [])
      .filter((r) => !selected || r.slug !== selected.slug)
      .map((r) => ({ value: r.slug, label: r.label })),
    [matrix.roles, selected],
  )

  const openEdit = (role) => {
    setSelected(role)
    setForm({
      label: role.label,
      slug: role.slug,
      description: role.description || '',
      needs_branch: role.needs_branch,
      color: role.color || '#6366f1',
      permissions: [...(role.permissions || [])],
      parent_slug: role.parent_slug || '',
      sort_order: role.sort_order ?? 50,
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
      const payload = {
        label: form.label,
        description: form.description,
        needs_branch: form.needs_branch,
        color: form.color,
        permissions: form.permissions,
        parent_slug: form.parent_slug || null,
        sort_order: form.sort_order,
      }
      if (selected) {
        await authApi.updateRoleDefinition(selected.slug, payload)
        setInfo('نقش به‌روز شد.')
      } else {
        await authApi.createRoleDefinition({ ...payload, slug: form.slug })
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
    if (role.slug === 'admin') return
    const builtinNote = role.is_builtin
      ? '\nاین نقش پیش‌فرض است؛ پس از حذف دوباره خودکار ساخته نمی‌شود.'
      : ''
    const msg = role.is_builtin
      ? `نقش پیش‌فرض «${role.label}» حذف شود؟${builtinNote}\nکاربران این نقش به «در انتظار تایید» منتقل می‌شوند.`
      : `نقش «${role.label}» حذف شود؟`
    if (!await confirm({
      title: 'حذف نقش',
      message: msg,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await authApi.deleteRoleDefinition(role.slug)
      setInfo('نقش حذف شد.')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const lockedRole = selected ? isLockedRole(selected) : false
  const isAdminRole = lockedRole || isFullAccessRole(selected, form.slug)

  const permOptions = isAdminRole
    ? matrix.permissions
    : (matrix.assignable_permissions?.length ? matrix.assignable_permissions : matrix.permissions)

  const permGroups = isAdminRole
    ? matrix.permission_groups
    : (matrix.assignable_permission_groups?.length
      ? matrix.assignable_permission_groups
      : matrix.permission_groups)

  const menuSections = isAdminRole
    ? matrix.menu_sections
    : (matrix.assignable_menu_sections?.length
      ? matrix.assignable_menu_sections
      : matrix.menu_sections)

  const toggleMenuSection = (section) => {
    const enabled = sectionHasMenuAccess({ permissions: form.permissions }, section)
    setForm((f) => ({
      ...f,
      permissions: toggleSectionPermissions(f.permissions, section, !enabled),
    }))
  }

  const renderPermCheckbox = (p) => (
    <label key={p.code} className="perm-item">
      <input
        type="checkbox"
        checked={isAdminRole || form.permissions.includes(p.code)}
        disabled={isAdminRole}
        onChange={() => togglePerm(p.code)}
      />
      <span>{p.label}</span>
    </label>
  )

  if (loading) return <div className="page"><p className="muted">در حال بارگذاری…</p></div>

  return (
    <div className="page roles-page">
      {error && <div className="alert-error">{error}</div>}
      {info && <div className="alert-info">{info}</div>}

      <Card title="سلسله‌مراتب سازمانی" actions={<Button onClick={openCreate}>+ نقش سفارشی</Button>}>
        <p className="muted roles-intro">
          پنل در چهار بخش «مدیران»، «فروشگاه»، «اداری» (شامل حسابداری) و «کارخانه» سازماندهی شده است.
        </p>

        {matrix.roles.length === 0 ? (
          <EmptyState message="نقشی تعریف نشده" />
        ) : (
          <div className="role-hierarchy">
            {roleTree.map((role) => (
              <RoleTreeCard
                key={role.slug}
                role={role}
                depth={0}
                onEdit={openEdit}
                onRemove={removeRole}
              />
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={selected ? `ویرایش ${selected.label}` : 'نقش جدید'}
        className="roles-modal"
      >
        <form onSubmit={save} className="form-grid roles-form">
          <Field label="عنوان نقش">
            <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} required />
          </Field>
          {!selected && (
            <Field label="شناسه (انگلیسی)">
              <input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="custom_role" />
            </Field>
          )}
          <Field label="نقش والد">
            <select
              value={form.parent_slug}
              onChange={(e) => setForm({ ...form, parent_slug: e.target.value })}
              disabled={lockedRole}
            >
              <option value="">— بدون والد (سطح بالا) —</option>
              {parentOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </Field>
          <Field label="ترتیب نمایش">
            <input
              type="number"
              min={0}
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) || 0 })}
            />
          </Field>
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

          <div className="menu-section-matrix">
            <h4>منوی پنل</h4>
            <p className="muted small" style={{ marginBottom: 12 }}>
              بخش‌های بدون تیک در منو نمایش داده نمی‌شوند و دسترسی API همان بخش قطع می‌شود.
            </p>
            {menuSections?.length ? (
              <div className="menu-section-grid">
                {menuSections.map((section) => {
                  const checked = isAdminRole || sectionHasMenuAccess({ permissions: form.permissions }, section)
                  return (
                    <label key={section.id} className="menu-section-item">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={isAdminRole}
                        onChange={() => toggleMenuSection(section)}
                      />
                      <span>{section.icon} {section.label}</span>
                    </label>
                  )
                })}
              </div>
            ) : (
              <p className="muted small">بخش منو تعریف نشده.</p>
            )}
          </div>

          <div className="perm-matrix">
            <h4>مجوزهای جزئی</h4>
            {isAdminRole && (
              <p className="muted small">این نقش همیشه همه مجوزها را دارد.</p>
            )}
            {permGroups?.length ? (
              <div className="perm-groups">
                {permGroups.map((group) => (
                  <div key={group.id} className="perm-group">
                    <h5 className="perm-group-title">{group.label}</h5>
                    <div className="perm-grid">
                      {group.permissions.map((p) => renderPermCheckbox(p))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="perm-grid">
                {permOptions.map((p) => renderPermCheckbox(p))}
              </div>
            )}
          </div>

          <div className="form-actions">
            <Button type="submit" disabled={saving || lockedRole}>{saving ? '…' : 'ذخیره'}</Button>
            <Button type="button" variant="ghost" onClick={() => setModalOpen(false)}>انصراف</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
