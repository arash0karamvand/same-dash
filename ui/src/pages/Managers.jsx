// فهرست مدیران — جدا از فروشندگان

import { useEffect, useState } from 'react'
import { staffApi } from '../api/client'
import { Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useConfig } from '../context/ConfigContext'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

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
  const [search, setSearch] = useState('')
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)

  const load = async ({ append = false, offset: nextOffset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const data = await staffApi.list(branch, 'manager', {
        search: search.trim() || undefined,
        offset: nextOffset,
        limit: PAGE_SIZE,
      })
      setManagers((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))
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
      <div className={fromLegacy("page")}>
        <Card title="مدیران">
          <div className={fromLegacy("alert-error")}>دسترسی مشاهده مدیران را ندارید.</div>
        </Card>
      </div>
    )
  }

  return (
    <div className={fromLegacy("page")}>
      <Card
        title="مدیران"
        actions={canManage ? <Button onClick={() => { setForm(EMPTY); setModalOpen(true) }}>+ مدیر</Button> : null}
      >
        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        <p className={fromLegacy("muted")} style={{ marginBottom: 12 }}>
          مدیران در فهرست فروشندگان نمایش داده نمی‌شوند.
        </p>
        <div className={fromLegacy("branch-tabs")}>
          {branchOptions.map((b) => (
            <button
              key={b.value}
              type="button"
              className={fromLegacy(`branch-tab ${branch === b.value ? 'active' : ''}`)}
              onClick={() => setBranch(b.value)}
            >
              {b.label}
            </button>
          ))}
        </div>
        <FilterBar>
          <Field label="جستجو">
            <input
              className={fromLegacy("search-input")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام یا موبایل…"
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </Field>
          <div className={fromLegacy("page-filters-actions")}>
            <Button type="button" variant="ghost" onClick={() => load()}>جستجو</Button>
          </div>
        </FilterBar>
        {loading ? <div className={fromLegacy("loading")}>در حال بارگذاری…</div> : managers.length === 0 ? (
          <EmptyState text={`مدیری در ${branchLabel} ثبت نشده.`} />
        ) : (
          <>
            <div className={fromLegacy("table-wrap staff-table-desktop")}>
              <table className={fromLegacy("table")}>
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
                      <td className={fromLegacy("ltr")}>{m.phone || '—'}</td>
                      <td>{m.branch_label}</td>
                      {canDelete && (
                        <td>
                          <button type="button" className={fromLegacy("link danger")} onClick={() => remove(m)}>
                            حذف
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={fromLegacy("staff-cards-mobile")}>
              {managers.map((m) => (
                <div key={m.id} className={fromLegacy("m-card")}>
                  <div className={fromLegacy("m-card-head")}>
                    <strong>{m.full_name}</strong>
                    <span className={fromLegacy("muted")}>{m.branch_label}</span>
                  </div>
                  <div className={fromLegacy("m-card-grid")}>
                    <div><span className={fromLegacy("muted")}>موبایل</span><span className={fromLegacy("ltr")}>{m.phone || '—'}</span></div>
                  </div>
                  {canDelete && (
                    <div className={fromLegacy("m-card-actions")}>
                      <button type="button" className={fromLegacy("link danger")} onClick={() => remove(m)}>حذف</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <LoadMoreButton
              hasMore={managers.length < total}
              loading={loadingMore}
              onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
            />
          </>
        )}
      </Card>
      <Modal title={`افزودن مدیر — ${branchLabel}`} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className={fromLegacy("form")}>
          <Field label="نام کامل">
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          </Field>
          <Field label="موبایل (اختیاری)">
            <input className={fromLegacy("ltr")} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <p className={fromLegacy("muted")}>بدون نام کاربری — فقط نام و شعبه ثبت می‌شود.</p>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>
    </div>
  )
}
