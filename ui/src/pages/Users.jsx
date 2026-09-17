// مدیریت کاربران — برد دپارتمان‌ها با تخصیص نقش و دسترسی فرعی

import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, Field, FilterBar, Modal, StatCard } from '../components/ui'
import PortalModuleMatrix from '../components/PortalModuleMatrix'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useMediaQuery } from '../hooks/useMediaQuery'
import {
  collectPortalPermissionCodes,
  toggleExtraOnlyPermissions,
  toggleExtraOnlyPortalPermissions,
} from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const ROLE_COLORS = {
  admin: '#7c3aed',
  ceo: '#b91c1c',
  co_ceo: '#8b5cf6',
  branch_supervisor: '#0ea5e9',
  sales_expert: '#6366f1',
  accounting_finance: '#10b981',
  factory_supervisor: '#78716c',
  freight_supervisor: '#ea580c',
  pending: '#d97706',
}

const DEPARTMENTS = [
  { id: 'managers', label: 'مدیران' },
  { id: 'shop', label: 'فروشگاه' },
  { id: 'office', label: 'اداری' },
  { id: 'factory', label: 'کارخانه' },
]

const NONE_DEPT_ID = ''
const BOARD_LIMIT = 500

const EMPTY_CREATE = {
  username: '',
  password: '',
  full_name: '',
  email: '',
}

function roleColor(role) {
  return ROLE_COLORS[role] || 'var(--muted)'
}

function needsBranch(role, roleMeta) {
  const meta = roleMeta.find((r) => r.value === role)
  return Boolean(meta?.needs_branch)
}

function extrasForPortal(permissions, portal) {
  if (!portal) return []
  const codes = new Set(collectPortalPermissionCodes(portal))
  return (permissions || []).filter((code) => codes.has(code))
}

function Flash({ type, message, onClose }) {
  if (!message) return null
  return (
    <div className={type === 'error' ? 'alert-error' : 'alert-info'} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span>{message}</span>
      <button type="button" className={fromLegacy('link')} onClick={onClose}>✕</button>
    </div>
  )
}

function UserBoardCard({ user, currentUserId, onEdit, onDeactivate }) {
  const secondary = (user.secondary_departments || []).filter((d) => d.id !== user.primary_department)
  return (
    <article className={fromLegacy(`user-card dept-user-card ${!user.is_active ? 'user-card-inactive' : ''}`)}>
      <div className={fromLegacy('user-card-head')}>
        <div>
          <strong className={fromLegacy('user-card-name')}>{user.full_name}</strong>
          <span className={fromLegacy('ltr muted user-card-username')}>@{user.username}</span>
        </div>
        <Badge color={roleColor(user.role)}>{user.role_label}</Badge>
      </div>
      {secondary.length > 0 && (
        <div className={fromLegacy('dept-user-chips')}>
          {secondary.map((dept) => (
            <span key={dept.id} className={fromLegacy('dept-chip')}>دسترسی {dept.label}</span>
          ))}
        </div>
      )}
      <div className={fromLegacy('user-card-actions')}>
        <Button variant="ghost" type="button" onClick={() => onEdit(user)}>ویرایش</Button>
        {user.id !== currentUserId && user.is_active && !user.is_superuser && (
          <button type="button" className={fromLegacy('link danger')} onClick={() => onDeactivate(user)}>غیرفعال</button>
        )}
        {user.id === currentUserId && <span className={fromLegacy('muted')}>حساب شما</span>}
      </div>
    </article>
  )
}

export default function Users() {
  const { user: currentUser } = useAuth()
  const confirm = useConfirm()
  const isMobile = useMediaQuery('(max-width: 900px)')
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState({ total: 0, active: 0, pending: 0, departments: {} })
  const [roles, setRoles] = useState([])
  const [portalModules, setPortalModules] = useState([])
  const [branches, setBranches] = useState([])
  const [orgRanks, setOrgRanks] = useState([])
  const [loading, setLoading] = useState(true)
  const [flash, setFlash] = useState({ type: '', message: '' })

  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [mobileDept, setMobileDept] = useState('shop')

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

  const [assign, setAssign] = useState(null)
  const [assigning, setAssigning] = useState(false)

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
        active: activeFilter || undefined,
        offset: 0,
        limit: BOARD_LIMIT,
      })
      setUsers(data.results || [])
      setStats(data.stats || { total: 0, active: 0, pending: 0, departments: {} })
    } catch (e) {
      showFlash('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [search, activeFilter, showFlash])

  useEffect(() => {
    loadMeta().catch((e) => showFlash('error', e.message))
  }, [loadMeta, showFlash])

  useEffect(() => {
    const t = setTimeout(() => loadUsers(), search ? 300 : 0)
    return () => clearTimeout(t)
  }, [loadUsers, search])

  const usersByDept = useMemo(() => {
    const grouped = { [NONE_DEPT_ID]: [] }
    DEPARTMENTS.forEach((d) => { grouped[d.id] = [] })
    users.forEach((u) => {
      const key = u.primary_department && grouped[u.primary_department] ? u.primary_department : NONE_DEPT_ID
      grouped[key].push(u)
    })
    return grouped
  }, [users])

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
      await authApi.createUser({ ...createForm, role: 'pending' })
      showFlash('success', `کاربر «${createForm.username}» ساخته شد و در بدون دسترسی است.`)
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

  const openAssign = (departmentId) => {
    setAssign({
      department: departmentId,
      step: 'pick',
      userId: '',
      mode: '',
      role: '',
      branch: 'branch_1',
      selected_permissions: [],
      error: '',
    })
  }

  const closeAssign = () => {
    if (!assigning) setAssign(null)
  }

  const assignTarget = useMemo(
    () => users.find((u) => String(u.id) === String(assign?.userId)) || null,
    [users, assign?.userId],
  )

  const assignPortal = useMemo(
    () => portalModules.find((p) => p.id === assign?.department) || null,
    [portalModules, assign?.department],
  )

  const assignRoles = useMemo(() => {
    if (!assign?.department) return []
    return roles.filter((r) => r.value !== 'pending' && (r.department || '') === assign.department)
  }, [roles, assign?.department])

  const pickAssignUser = (userId) => {
    const person = users.find((u) => String(u.id) === String(userId))
    if (!person) {
      setAssign((a) => ({ ...a, userId, error: '' }))
      return
    }
    if (person.id === currentUser?.id) {
      setAssign((a) => ({ ...a, userId: '', error: 'نمی‌توانید دپارتمان خودتان را از اینجا تغییر دهید.' }))
      return
    }
    if (person.grants_full_access || person.is_superuser) {
      if (assign.department !== 'managers') {
        setAssign((a) => ({ ...a, userId: '', error: 'کاربران با دسترسی کامل فقط در دپارتمان مدیران می‌مانند.' }))
        return
      }
      setAssign((a) => ({ ...a, userId, mode: 'keep', step: 'keep', error: '', selected_permissions: [] }))
      return
    }
    if (!person.primary_department) {
      const firstRole = roles.find((r) => r.value !== 'pending' && (r.department || '') === assign.department)
      setAssign((a) => ({
        ...a,
        userId,
        mode: 'replace',
        step: 'replace',
        role: firstRole?.value || '',
        error: '',
      }))
      return
    }
    setAssign((a) => ({ ...a, userId, step: 'mode', mode: '', error: '' }))
  }

  const startReplace = () => {
    const firstRole = assignRoles[0]
    setAssign((a) => ({ ...a, mode: 'replace', step: 'replace', role: firstRole?.value || '', error: '' }))
  }

  const startKeep = () => {
    if (!assignTarget || !assignPortal) return
    setAssign((a) => ({
      ...a,
      mode: 'keep',
      step: 'keep',
      selected_permissions: extrasForPortal(assignTarget.extra_permissions || [], assignPortal),
      error: '',
    }))
  }

  const submitAssign = async (e) => {
    e.preventDefault()
    if (!assign?.userId || !assign.department) return
    if (assign.step === 'replace' && !assign.role) {
      setAssign((a) => ({ ...a, error: 'انتخاب نقش الزامی است.' }))
      return
    }
    if (assign.step === 'keep' && assignTarget && !assignTarget.grants_full_access) {
      const selected = extrasForPortal(assign.selected_permissions, assignPortal)
      if (!selected.length) {
        setAssign((a) => ({ ...a, error: 'باید حتماً یکی را انتخاب کنی' }))
        return
      }
    }
    setAssigning(true)
    try {
      const payload = {
        department: assign.department,
        mode: assign.mode || 'replace',
      }
      if (payload.mode === 'replace') {
        payload.role = assign.role
        if (needsBranch(assign.role, roles)) payload.branch = assign.branch
      } else {
        payload.selected_permissions = extrasForPortal(assign.selected_permissions, assignPortal)
      }
      await authApi.assignDepartment(assign.userId, payload)
      const deptLabel = DEPARTMENTS.find((d) => d.id === assign.department)?.label || assign.department
      showFlash('success', `${assignTarget?.full_name || 'کاربر'} به «${deptLabel}» اضافه شد.`)
      setAssign(null)
      loadUsers()
    } catch (err) {
      setAssign((a) => ({ ...a, error: err.message }))
    } finally {
      setAssigning(false)
    }
  }

  const toggleAssignPortal = (_portal, enable) => {
    if (!assignPortal) return
    setAssign((a) => ({
      ...a,
      error: '',
      selected_permissions: toggleExtraOnlyPortalPermissions(
        [],
        a.selected_permissions,
        assignPortal,
        enable,
      ),
    }))
  }

  const toggleAssignModule = (mod, enable) => {
    setAssign((a) => ({
      ...a,
      error: '',
      selected_permissions: toggleExtraOnlyPermissions(
        [],
        a.selected_permissions,
        mod,
        enable,
      ),
    }))
  }

  const addCandidateOptions = useMemo(() => {
    if (!assign?.department) return []
    return users
      .filter((u) => (u.primary_department || '') !== assign.department)
      .map((u) => ({
        value: String(u.id),
        label: u.full_name,
        hint: u.primary_department
          ? `${u.department_label} / ${u.role_label}`
          : 'بدون دسترسی',
      }))
  }, [users, assign?.department])

  const deptColumns = [...DEPARTMENTS, { id: NONE_DEPT_ID, label: 'بدون دسترسی' }]
  const visibleColumns = isMobile
    ? deptColumns.filter((d) => d.id === mobileDept)
    : DEPARTMENTS

  const renderColumn = (dept) => {
    const members = usersByDept[dept.id] || []
    const count = stats.departments?.[dept.id === NONE_DEPT_ID ? 'none' : dept.id] ?? members.length
    return (
      <section key={dept.id || 'none'} className={fromLegacy('dept-column')}>
        <header className={fromLegacy('dept-column-head')}>
          <div>
            <h3>{dept.label}</h3>
            <span className={fromLegacy('muted small')}>{count} نفر</span>
          </div>
          {dept.id !== NONE_DEPT_ID && (
            <Button type="button" variant="ghost" onClick={() => openAssign(dept.id)}>+ افزودن</Button>
          )}
        </header>
        <div className={fromLegacy('dept-column-body')}>
          {members.length === 0 ? (
            <p className={fromLegacy('muted small')}>هنوز کسی اینجا نیست.</p>
          ) : members.map((u) => (
            <UserBoardCard
              key={u.id}
              user={u}
              currentUserId={currentUser?.id}
              onEdit={openEdit}
              onDeactivate={deactivate}
            />
          ))}
        </div>
      </section>
    )
  }

  const assignDeptLabel = DEPARTMENTS.find((d) => d.id === assign?.department)?.label || ''

  return (
    <div className={fromLegacy('page users-page')}>
      <div className={fromLegacy('stat-grid users-stats')}>
        <StatCard label="کل کاربران" value={stats.total} accent="var(--accent)" />
        <StatCard label="فعال" value={stats.active} accent="var(--success)" />
        <StatCard label="بدون دسترسی" value={stats.departments?.none ?? stats.pending} accent="var(--warning)" />
      </div>

      <Card
        title="کاربران بر اساس دپارتمان"
        actions={<Button onClick={() => setCreateOpen(true)}>+ کاربر جدید</Button>}
      >
        <Flash type={flash.type} message={flash.message} onClose={() => setFlash({ type: '', message: '' })} />

        <FilterBar>
          <Field label="جستجو">
            <input
              className={fromLegacy('search-input')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام کاربری، نام یا ایمیل…"
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

        {isMobile && (
          <div className={fromLegacy('dept-mobile-tabs')} role="tablist">
            {deptColumns.map((dept) => (
              <button
                key={dept.id || 'none'}
                type="button"
                className={fromLegacy(`dept-mobile-tab ${mobileDept === dept.id ? 'is-active' : ''}`)}
                onClick={() => setMobileDept(dept.id)}
              >
                {dept.label}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className={fromLegacy('loading')}>در حال بارگذاری…</div>
        ) : (
          <>
            <div className={fromLegacy('dept-board')}>
              {visibleColumns.map(renderColumn)}
            </div>
            {!isMobile && (
              <div className={fromLegacy('dept-board dept-board-none')}>
                {renderColumn({ id: NONE_DEPT_ID, label: 'بدون دسترسی' })}
              </div>
            )}
          </>
        )}
      </Card>

      {isSystemAdmin && (
        <Card title="منطقه خطر">
          <div className={fromLegacy('danger-zone')}>
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
          <p className={fromLegacy('muted')} style={{ marginBottom: 16, lineHeight: 1.7 }}>
            با این کار تمام اطلاعات به‌صورت دائمی از دیتابیس پاک می‌شود (نه حذف نرم).
            فقط حساب مدیر سیستم باقی می‌ماند. برای ادامه، عبارت <strong>پاکسازی</strong> را بنویسید.
          </p>
          <Field label="تأیید">
            <input
              className={fromLegacy('ltr')}
              value={resetConfirm}
              onChange={(e) => setResetConfirm(e.target.value)}
              placeholder="پاکسازی"
              autoComplete="off"
            />
          </Field>
          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={() => { setResetOpen(false); setResetConfirm('') }} disabled={resetting}>
              انصراف
            </Button>
            <Button type="submit" variant="danger" disabled={resetting || resetConfirm !== 'پاکسازی'}>
              {resetting ? 'در حال پاک‌سازی…' : 'پاک‌سازی قطعی'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal title="کاربر جدید" open={createOpen} onClose={() => setCreateOpen(false)}>
        <form onSubmit={createUser} className={fromLegacy('form')}>
          <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
            کاربر بدون دسترسی ساخته می‌شود. بعد از ساخت، از دکمه افزودن هر دپارتمان نقش بدهید.
          </p>
          <Field label="نام کاربری">
            <input
              className={fromLegacy('ltr')}
              value={createForm.username}
              onChange={(e) => setCreateForm({ ...createForm, username: e.target.value.trim() })}
              required
              minLength={3}
              autoComplete="off"
            />
          </Field>
          <Field label="رمز عبور">
            <input
              className={fromLegacy('ltr')}
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              required
              minLength={8}
              autoComplete="new-password"
            />
            <span className={fromLegacy('muted')}>حداقل ۸ کاراکتر</span>
          </Field>
          <Field label="نام کامل">
            <input
              value={createForm.full_name}
              onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
            />
          </Field>
          <Field label="ایمیل (اختیاری)">
            <input
              className={fromLegacy('ltr')}
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
            />
          </Field>
          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>انصراف</Button>
            <Button type="submit" disabled={creating}>{creating ? 'در حال ساخت…' : 'ساخت کاربر'}</Button>
          </div>
        </form>
      </Modal>

      <Modal
        title={assign ? `افزودن به ${assignDeptLabel}` : ''}
        open={Boolean(assign)}
        onClose={closeAssign}
        wide={assign?.step === 'keep'}
      >
        {assign && (
          <form onSubmit={submitAssign} className={fromLegacy('form')}>
            {assign.error && <div className="alert-error">{assign.error}</div>}

            {assign.step === 'pick' && (
              <Field label="انتخاب فرد">
                <Select
                  value={assign.userId}
                  onChange={pickAssignUser}
                  options={addCandidateOptions}
                  placeholder="کسی که در این دپارتمان نیست"
                  required
                />
              </Field>
            )}

            {assign.step === 'mode' && assignTarget && (
              <>
                <p>
                  «{assignTarget.full_name}» الان در «{assignTarget.department_label || 'بدون دسترسی'}» است.
                </p>
                <div className={fromLegacy('dept-mode-actions')}>
                  <Button type="button" onClick={startReplace}>انتقال با قطع دسترسی</Button>
                  <Button type="button" variant="ghost" onClick={startKeep}>تغییر دپارتمان با حفظ دسترسی</Button>
                </div>
              </>
            )}

            {assign.step === 'replace' && (
              <>
                <p className={fromLegacy('muted small')}>
                  همه دسترسی‌های قبلی قطع می‌شود. نقش جدید این دپارتمان را انتخاب کنید.
                </p>
                <Field label="نقش">
                  <Select
                    value={assign.role}
                    onChange={(v) => setAssign((a) => ({ ...a, role: v, error: '' }))}
                    options={assignRoles.map((r) => ({ value: r.value, label: r.label }))}
                    placeholder="انتخاب نقش"
                    required
                  />
                </Field>
                {needsBranch(assign.role, roles) && (
                  <Field label="شعبه">
                    <Select
                      value={assign.branch}
                      onChange={(v) => setAssign((a) => ({ ...a, branch: v }))}
                      options={branches}
                    />
                  </Field>
                )}
              </>
            )}

            {assign.step === 'keep' && assignTarget?.grants_full_access && (
              <p>دسترسی کامل این کاربر حفظ می‌شود و دپارتمان اصلی مدیران می‌ماند.</p>
            )}

            {assign.step === 'keep' && assignPortal && assignTarget && !assignTarget.grants_full_access && (
              <div className={fromLegacy('menu-section-matrix user-access-matrix')}>
                <h4>در {assignDeptLabel} به چه چیزهایی دسترسی دارد؟</h4>
                <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
                  حداقل یک مورد را انتخاب کنید. دسترسی دپارتمان‌های دیگر حفظ می‌شود.
                </p>
                <PortalModuleMatrix
                  portals={[assignPortal]}
                  permissions={assign.selected_permissions}
                  basePermissions={[]}
                  defaultExpanded={[assign.department]}
                  onTogglePortal={toggleAssignPortal}
                  onToggleModule={toggleAssignModule}
                />
              </div>
            )}

            <div className={fromLegacy('form-actions')}>
              <Button type="button" variant="ghost" onClick={closeAssign} disabled={assigning}>انصراف</Button>
              {assign.step !== 'pick' && assign.step !== 'mode' && (
                <Button type="submit" disabled={assigning}>
                  {assigning ? 'در حال ذخیره…' : 'تأیید'}
                </Button>
              )}
            </div>
          </form>
        )}
      </Modal>

      <Modal title={editUser ? `ویرایش — ${editUser.username}` : ''} open={Boolean(editUser)} onClose={closeEdit}>
        {editForm && (
          <form onSubmit={saveEdit} className={fromLegacy('form')}>
            <Field label="نام کامل">
              <input
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              />
            </Field>
            <Field label="ایمیل">
              <input
                className={fromLegacy('ltr')}
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
                  <label className={fromLegacy('checkbox-row')}>
                    <input
                      type="checkbox"
                      checked={editForm.is_active}
                      onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                    />
                    <span>حساب فعال است</span>
                  </label>
                </Field>

                {canEditExtraPermissions && portalModules.length > 0 && (
                  <div className={fromLegacy('menu-section-matrix user-access-matrix')}>
                    <div className={fromLegacy('user-access-matrix-head')}>
                      <h4>دسترسی ماژولار</h4>
                      <Badge color={roleColor(editForm.role)}>{editRoleLabel}</Badge>
                    </div>
                    <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
                      ماژول‌های تیک‌خورده از نقش «{editRoleLabel}» می‌آیند و قابل حذف نیستند.
                      {' '}بقیه را می‌توانید فقط برای این کاربر اضافه کنید — از جمله دسترسی جزئی به دپارتمان دیگر.
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
              <p className={fromLegacy('muted')}>نقش و وضعیت حساب خودتان از اینجا قابل تغییر نیست.</p>
            )}

            {!isSelf && (
              <Field label="رمز عبور جدید (اختیاری)">
                <input
                  className={fromLegacy('ltr')}
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="برای بازنشانی پر کنید"
                />
              </Field>
            )}

            <div className={fromLegacy('form-actions')}>
              <Button type="button" variant="ghost" onClick={closeEdit}>انصراف</Button>
              <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}</Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
