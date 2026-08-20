// مدیریت کاربران — UX بازطراحی‌شده با مودال، فیلتر و ویرایش یکپارچه

import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import PortalModuleMatrix from '../components/PortalModuleMatrix'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate } from '../utils/format'
import { toggleExtraOnlyPermissions, toggleExtraOnlyPortalPermissions } from '../utils/permissions'

const ROLE_COLORS = {
  admin: '#7c3aed',
  sales_manager: '#2563eb',
  accountant: '#059669',
  operator: 'var(--accent)',
  pending: '#d97706',
}

const EMPTY_CREATE = {
  username: '',
  password: '',
  full_name: '',
  email: '',
  role: 'operator',
  branch: 'branch_1',
}

function roleColor(role) {
  return ROLE_COLORS[role] || 'var(--muted)'
}

function needsBranch(role, roleMeta) {
  const meta = roleMeta.find((r) => r.value === role)
  return meta?.needs_branch ?? ['operator', 'sales_manager', 'accountant'].includes(role)
}

function Flash({ type, message, onClose }) {
  if (!message) return null
  return (
    <div className={type === 'error' ? 'alert-error' : 'alert-info'} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span>{message}</span>
      <button type="button" className="link" onClick={onClose}>✕</button>
    </div>
  )
}

export default function Users() {
  const { user: currentUser } = useAuth()
  const confirm = useConfirm()
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState({ total: 0, active: 0, pending: 0 })
  const [roles, setRoles] = useState([])
  const [portalModules, setPortalModules] = useState([])
  const [branches, setBranches] = useState([])
  const [orgRanks, setOrgRanks] = useState([])
  const [loading, setLoading] = useState(true)
  const [flash, setFlash] = useState({ type: '', message: '' })

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [creating, setCreating] = useState(false)

  const [editUser, setEditUser] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const [resetOpen, setResetOpen] = useState(false)
  const [resetConfirm, setResetConfirm] = useState('')
  const [resetting, setResetting] = useState(false)

  const isSystemAdmin = currentUser?.is_superuser || currentUser?.role === 'admin'

  const showFlash = useCallback((type, message) => {
    setFlash({ type, message })
    if (message) setTimeout(() => setFlash({ type: '', message: '' }), 4000)
  }, [])

  const loadMeta = useCallback(async () => {
    const [data, ranks] = await Promise.all([authApi.roles(), authApi.orgRanks()])
    setRoles(data.results || [])
    setPortalModules(data.assignable_portal_modules || [])
    setBranches(data.branches || [])
    setOrgRanks(ranks.results || [])
  }, [])

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const data = await authApi.users({
        search: search.trim() || undefined,
        role: roleFilter || undefined,
        active: activeFilter || undefined,
      })
      setUsers(data.results || [])
      setStats(data.stats || { total: 0, active: 0, pending: 0 })
    } catch (e) {
      showFlash('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [search, roleFilter, activeFilter, showFlash])

  useEffect(() => {
    loadMeta().catch((e) => showFlash('error', e.message))
  }, [loadMeta, showFlash])

  useEffect(() => {
    const t = setTimeout(loadUsers, search ? 300 : 0)
    return () => clearTimeout(t)
  }, [loadUsers, search])

  const openEdit = (u) => {
    setEditUser(u)
    setEditForm({
      full_name: u.full_name,
      email: u.email || '',
      role: u.role,
      branch: u.branch || 'branch_1',
      is_active: u.is_active,
      job_title: u.job_title || '',
      manager_id: u.manager_id || '',
      org_rank_id: u.org_rank_id || '',
      extra_permissions: [...(u.extra_permissions || [])],
    })
    setNewPassword('')
  }

  const closeEdit = () => {
    setEditUser(null)
    setEditForm(null)
    setNewPassword('')
  }

  const createUser = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const payload = { ...createForm }
      if (!needsBranch(createForm.role, roles)) delete payload.branch
      await authApi.createUser(payload)
      showFlash('success', `کاربر «${createForm.username}» ساخته شد.`)
      setCreateForm(EMPTY_CREATE)
      setCreateOpen(false)
      loadUsers()
    } catch (err) {
      showFlash('error', err.message)
    } finally {
      setCreating(false)
    }
  }

  const saveEdit = async (e) => {
    e.preventDefault()
    if (!editUser || !editForm) return
    setSaving(true)
    try {
      const payload = {
        full_name: editForm.full_name,
        email: editForm.email,
        role: editForm.role,
        is_active: editForm.is_active,
      }
      if (needsBranch(editForm.role, roles)) {
        payload.branch = editForm.branch
      }
      payload.job_title = editForm.job_title
      payload.manager_id = editForm.manager_id || null
      payload.org_rank_id = editForm.org_rank_id || null
      if (!editUser.grants_full_access && !editUser.is_superuser) {
        payload.extra_permissions = editForm.extra_permissions
      }
      await authApi.updateUser(editUser.id, payload)
      if (newPassword.trim().length >= 8) {
        await authApi.resetPassword(editUser.id, newPassword.trim())
      }
      showFlash('success', `تغییرات «${editUser.username}» ذخیره شد.`)
      closeEdit()
      loadUsers()
    } catch (err) {
      showFlash('error', err.message)
    } finally {
      setSaving(false)
    }
  }

  const deactivate = async (u) => {
    if (!await confirm({
      title: 'غیرفعال‌سازی کاربر',
      message: `کاربر «${u.full_name}» غیرفعال شود؟ دیگر نمی‌تواند وارد شود.`,
      confirmText: 'بله، غیرفعال شود',
      variant: 'danger',
    })) return
    try {
      await authApi.deactivateUser(u.id)
      showFlash('success', `کاربر «${u.username}» غیرفعال شد.`)
      loadUsers()
    } catch (err) {
      showFlash('error', err.message)
    }
  }

  const handleResetData = async (e) => {
    e.preventDefault()
    if (resetConfirm !== 'پاکسازی') {
      showFlash('error', 'برای تأیید، عبارت «پاکسازی» را دقیقاً وارد کنید.')
      return
    }
    setResetting(true)
    try {
      await authApi.resetBusinessData(resetConfirm)
      showFlash('success', 'همه داده‌ها به‌صورت دائمی حذف شدند. فقط مدیر سیستم باقی ماند.')
      setResetOpen(false)
      setResetConfirm('')
      loadUsers()
    } catch (err) {
      showFlash('error', err.message)
    } finally {
      setResetting(false)
    }
  }

  const selectedRoleMeta = useMemo(
    () => roles.find((r) => r.value === (editForm?.role || createForm.role)),
    [roles, editForm, createForm.role],
  )

  const isSelf = editUser?.id === currentUser?.id
  const canEditExtraPermissions = editUser && !isSelf && !editUser.grants_full_access && !editUser.is_superuser

  const editRolePermissions = useMemo(() => {
    if (!editForm?.role) return []
    const meta = roles.find((r) => r.value === editForm.role)
    return meta?.permissions || []
  }, [editForm?.role, roles])

  const editRoleLabel = useMemo(() => {
    if (!editForm?.role) return ''
    const meta = roles.find((r) => r.value === editForm.role)
    return meta?.label || editUser?.role_label || editForm.role
  }, [editForm?.role, editUser?.role_label, roles])

  const toggleExtraPortal = (portal, enable) => {
    setEditForm((f) => {
      const rolePerms = roles.find((r) => r.value === f.role)?.permissions || []
      return {
        ...f,
        extra_permissions: toggleExtraOnlyPortalPermissions(
          rolePerms,
          f.extra_permissions,
          portal,
          enable,
        ),
      }
    })
  }

  const toggleExtraModule = (mod, enable) => {
    setEditForm((f) => {
      const rolePerms = roles.find((r) => r.value === f.role)?.permissions || []
      return {
        ...f,
        extra_permissions: toggleExtraOnlyPermissions(
          rolePerms,
          f.extra_permissions,
          mod,
          enable,
        ),
      }
    })
  }

  return (
    <div className="page users-page">
      <div className="stat-grid users-stats">
        <StatCard label="کل کاربران" value={stats.total} accent="var(--accent)" />
        <StatCard label="فعال" value={stats.active} accent="var(--success)" />
        <StatCard label="در انتظار نقش" value={stats.pending} accent="var(--warning)" />
      </div>

      <Card
        title="کاربران و نقش‌ها"
        actions={<Button onClick={() => setCreateOpen(true)}>+ کاربر جدید</Button>}
      >
        <Flash type={flash.type} message={flash.message} onClose={() => setFlash({ type: '', message: '' })} />

        <FilterBar>
          <Field label="جستجو">
            <input
              className="search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام کاربری، نام یا ایمیل…"
            />
          </Field>
          <Field label="نقش">
            <Select
              value={roleFilter}
              onChange={setRoleFilter}
              options={[{ value: '', label: 'همه نقش‌ها' }, ...roles]}
              placeholder="همه نقش‌ها"
            />
          </Field>
          <Field label="وضعیت">
            <Select
              value={activeFilter}
              onChange={setActiveFilter}
              options={[
                { value: '', label: 'همه' },
                { value: '1', label: 'فعال' },
                { value: '0', label: 'غیرفعال' },
              ]}
              placeholder="همه"
            />
          </Field>
        </FilterBar>

        {loading ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : users.length === 0 ? (
          <EmptyState text="کاربری با این فیلتر یافت نشد." />
        ) : (
          <>
            <div className="user-cards">
              {users.map((u) => (
                <article key={u.id} className={`user-card ${!u.is_active ? 'user-card-inactive' : ''}`}>
                  <div className="user-card-head">
                    <div>
                      <strong className="user-card-name">{u.full_name}</strong>
                      <span className="ltr muted user-card-username">@{u.username}</span>
                    </div>
                    <Badge color={roleColor(u.role)}>{u.role_label}</Badge>
                  </div>
                  <ul className="user-card-meta">
                    <li><span>شعبه</span><span>{u.branch_label}</span></li>
                    <li><span>ایمیل</span><span className="ltr">{u.email || '—'}</span></li>
                    <li><span>آخرین ورود</span><span>{u.last_login ? formatDate(u.last_login) : '—'}</span></li>
                    <li>
                      <span>وضعیت</span>
                      <span>{u.is_active ? 'فعال' : 'غیرفعال'}{u.is_superuser ? ' · superuser' : ''}</span>
                    </li>
                  </ul>
                  <div className="user-card-actions">
                    <Button variant="ghost" type="button" onClick={() => openEdit(u)}>ویرایش</Button>
                    {u.id !== currentUser?.id && u.is_active && !u.is_superuser && (
                      <button type="button" className="link danger" onClick={() => deactivate(u)}>غیرفعال</button>
                    )}
                    {u.id === currentUser?.id && <span className="muted">حساب شما</span>}
                  </div>
                </article>
              ))}
            </div>

            <div className="users-table-wrap">
              <table className="table users-table">
                <thead>
                  <tr>
                    <th>کاربر</th>
                    <th>نقش</th>
                    <th>شعبه</th>
                    <th>وضعیت</th>
                    <th>آخرین ورود</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className={!u.is_active ? 'row-inactive' : ''}>
                      <td>
                        <div className="user-cell-name">{u.full_name}</div>
                        <div className="ltr muted user-cell-sub">@{u.username}</div>
                      </td>
                      <td><Badge color={roleColor(u.role)}>{u.role_label}</Badge></td>
                      <td>{u.branch_label}</td>
                      <td>{u.is_active ? 'فعال' : 'غیرفعال'}</td>
                      <td>{u.last_login ? formatDate(u.last_login) : '—'}</td>
                      <td className="row-actions">
                        <button type="button" className="link" onClick={() => openEdit(u)}>ویرایش</button>
                        {u.id !== currentUser?.id && u.is_active && !u.is_superuser && (
                          <button type="button" className="link danger" onClick={() => deactivate(u)}>غیرفعال</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      {isSystemAdmin && (
        <Card title="منطقه خطر">
          <div className="danger-zone">
            <h3>پاک‌سازی کامل داده‌ها</h3>
            <p>
              همه اطلاعات سیستم (مشتریان، فروش‌ها، حسابداری، پیامک‌ها، حضور و غیاب، محصولات،
              سطوح باشگاه، فروشندگان و کاربران) به‌صورت دائمی و فیزیکی حذف می‌شوند.
              فقط حساب مدیر سیستم باقی می‌ماند. بازیابی ممکن نیست.
            </p>
            <Button type="button" variant="danger" onClick={() => setResetOpen(true)}>
              پاک‌سازی همه داده‌ها
            </Button>
          </div>
        </Card>
      )}

      <Modal
        open={resetOpen}
        title="تأیید پاک‌سازی داده‌ها"
        onClose={() => { if (!resetting) { setResetOpen(false); setResetConfirm('') } }}
      >
        <form onSubmit={handleResetData}>
          <p className="muted" style={{ marginBottom: 16, lineHeight: 1.7 }}>
            با این کار تمام اطلاعات به‌صورت دائمی از دیتابیس پاک می‌شود (نه حذف نرم).
            فقط حساب مدیر سیستم باقی می‌ماند. برای ادامه، عبارت <strong>پاکسازی</strong> را بنویسید.
          </p>
          <Field label="تأیید">
            <input
              className="ltr"
              value={resetConfirm}
              onChange={(e) => setResetConfirm(e.target.value)}
              placeholder="پاکسازی"
              autoComplete="off"
            />
          </Field>
          <div className="form-actions">
            <Button
              type="button"
              variant="ghost"
              onClick={() => { setResetOpen(false); setResetConfirm('') }}
              disabled={resetting}
            >
              انصراف
            </Button>
            <Button
              type="submit"
              variant="danger"
              disabled={resetting || resetConfirm !== 'پاکسازی'}
            >
              {resetting ? 'در حال پاک‌سازی…' : 'پاک‌سازی قطعی'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal title="کاربر جدید" open={createOpen} onClose={() => setCreateOpen(false)}>
        <form onSubmit={createUser} className="form">
          <Field label="نام کاربری">
            <input
              className="ltr"
              value={createForm.username}
              onChange={(e) => setCreateForm({ ...createForm, username: e.target.value.trim() })}
              required
              minLength={3}
              autoComplete="off"
            />
          </Field>
          <Field label="رمز عبور">
            <input
              className="ltr"
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              required
              minLength={8}
              autoComplete="new-password"
            />
            <span className="muted">حداقل ۸ کاراکتر</span>
          </Field>
          <Field label="نام کامل">
            <input
              value={createForm.full_name}
              onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
            />
          </Field>
          <Field label="ایمیل (اختیاری)">
            <input
              className="ltr"
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
            />
          </Field>
          <Field label="نقش">
            <Select
              value={createForm.role}
              onChange={(v) => setCreateForm({ ...createForm, role: v })}
              options={roles}
            />
            {selectedRoleMeta?.description && (
              <span className="role-hint muted">{selectedRoleMeta.description}</span>
            )}
          </Field>
          {needsBranch(createForm.role, roles) && (
            <Field label="شعبه">
              <Select
                value={createForm.branch}
                onChange={(v) => setCreateForm({ ...createForm, branch: v })}
                options={branches}
              />
            </Field>
          )}
          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>انصراف</Button>
            <Button type="submit" disabled={creating}>{creating ? 'در حال ساخت…' : 'ساخت کاربر'}</Button>
          </div>
        </form>
      </Modal>

      <Modal title={editUser ? `ویرایش — ${editUser.username}` : ''} open={Boolean(editUser)} onClose={closeEdit}>
        {editForm && (
          <form onSubmit={saveEdit} className="form">
            <Field label="نام کامل">
              <input
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              />
            </Field>
            <Field label="ایمیل">
              <input
                className="ltr"
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              />
            </Field>

            {!isSelf && (
              <>
                <Field label="نقش">
                  <Select
                    value={editForm.role}
                    onChange={(v) => setEditForm({ ...editForm, role: v })}
                    options={roles}
                    disabled={editUser?.is_superuser}
                  />
                  {roles.find((r) => r.value === editForm.role)?.description && (
                    <span className="role-hint muted">
                      {roles.find((r) => r.value === editForm.role).description}
                    </span>
                  )}
                </Field>
                {needsBranch(editForm.role, roles) && (
                  <Field label="شعبه">
                    <Select
                      value={editForm.branch}
                      onChange={(v) => setEditForm({ ...editForm, branch: v })}
                      options={branches}
                    />
                  </Field>
                )}
                <Field label="عنوان شغلی">
                  <input value={editForm.job_title} onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })} placeholder="مثلاً سرپرست شعبه" />
                </Field>
                <Field label="مدیر مستقیم">
                  <Select
                    value={editForm.manager_id}
                    onChange={(v) => setEditForm({ ...editForm, manager_id: v })}
                    options={[
                      { value: '', label: '— بدون مدیر —' },
                      ...users.filter((u) => u.id !== editUser?.id).map((u) => ({
                        value: String(u.id),
                        label: `${u.full_name} (${u.role_label})`,
                      })),
                    ]}
                    placeholder="— بدون مدیر —"
                  />
                </Field>
                <Field label="رتبه سازمانی">
                  <Select
                    value={editForm.org_rank_id}
                    onChange={(v) => setEditForm({ ...editForm, org_rank_id: v })}
                    options={[
                      { value: '', label: '—' },
                      ...orgRanks.map((r) => ({ value: String(r.id), label: r.name })),
                    ]}
                    placeholder="—"
                  />
                </Field>
                <Field label="وضعیت حساب">
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={editForm.is_active}
                      onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                    />
                    <span>حساب فعال است</span>
                  </label>
                </Field>

                {canEditExtraPermissions && portalModules.length > 0 && (
                  <div className="menu-section-matrix user-access-matrix">
                    <div className="user-access-matrix-head">
                      <h4>دسترسی ماژولار</h4>
                      <Badge color={roleColor(editForm.role)}>{editRoleLabel}</Badge>
                    </div>
                    <p className="muted small" style={{ marginBottom: 12 }}>
                      ماژول‌های تیک‌خورده از نقش «{editRoleLabel}» می‌آیند و قابل حذف نیستند.
                      {' '}بقیه را می‌توانید فقط برای این کاربر اضافه کنید.
                    </p>
                    <PortalModuleMatrix
                      portals={portalModules}
                      permissions={editForm.extra_permissions}
                      basePermissions={editRolePermissions}
                      onTogglePortal={toggleExtraPortal}
                      onToggleModule={toggleExtraModule}
                    />
                  </div>
                )}
              </>
            )}

            {isSelf && (
              <p className="muted">نقش و وضعیت حساب خودتان از اینجا قابل تغییر نیست.</p>
            )}

            {!isSelf && (
              <Field label="رمز عبور جدید (اختیاری)">
                <input
                  className="ltr"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="برای بازنشانی پر کنید"
                />
              </Field>
            )}

            <div className="form-actions">
              <Button type="button" variant="ghost" onClick={closeEdit}>انصراف</Button>
              <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}</Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
