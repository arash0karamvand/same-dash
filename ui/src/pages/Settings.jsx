// تنظیمات سیستم — شعب، گزینه‌ها، منو (همه از MySQL)

import { useCallback, useEffect, useState } from 'react'
import { configApi } from '../api/client'
import { useConfig } from '../context/ConfigContext'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import LogoSettings from '../components/LogoSettings'
import { isSystemAdmin } from '../utils/permissions'

const LOOKUP_CATEGORIES = [
  { id: 'payment_method', label: 'روش پرداخت' },
  { id: 'payment_status', label: 'وضعیت پرداخت' },
  { id: 'order_kind', label: 'نوع سفارش' },
  { id: 'order_status', label: 'وضعیت سفارش' },
  { id: 'discount_type', label: 'نوع تخفیف' },
  { id: 'staff_kind', label: 'نوع پرسنل' },
]

const EMPTY_BRANCH = { code: '', label: '', color: 'var(--accent)', sort_order: 0 }
const EMPTY_LOOKUP = { category: 'payment_method', code: '', label: '', sort_order: 0 }

export default function Settings() {
  const { refresh: refreshConfig, moduleTree } = useConfig()
  const [tab, setTab] = useState('branches')
  const [branches, setBranches] = useState([])
  const [lookups, setLookups] = useState([])
  const [menuSections, setMenuSections] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [branchModal, setBranchModal] = useState(false)
  const [lookupModal, setLookupModal] = useState(false)
  const [branchForm, setBranchForm] = useState(EMPTY_BRANCH)
  const [lookupForm, setLookupForm] = useState(EMPTY_LOOKUP)
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [lookupCategory, setLookupCategory] = useState('payment_method')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [b, l, m] = await Promise.all([
        configApi.branches(),
        configApi.lookups(),
        configApi.menuSections(),
      ])
      setBranches(b.results || [])
      setLookups(l.results || [])
      setMenuSections(m.results || [])
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const afterSave = async () => {
    await load()
    await refreshConfig()
  }

  const saveBranch = async (e) => {
    e.preventDefault()
    try {
      if (selectedBranch) {
        await configApi.updateBranch(selectedBranch.id, branchForm)
        setInfo('شعبه به‌روز شد.')
      } else {
        await configApi.createBranch(branchForm)
        setInfo('شعبه جدید ساخته شد.')
      }
      setBranchModal(false)
      await afterSave()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveLookup = async (e) => {
    e.preventDefault()
    try {
      await configApi.createLookup({ ...lookupForm, category: lookupCategory })
      setInfo('گزینه جدید ساخته شد.')
      setLookupModal(false)
      await afterSave()
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleLookup = async (item) => {
    try {
      const next = !item.is_active
      await configApi.updateLookup(item.id, { is_active: next })
      setInfo(next ? 'گزینه فعال شد.' : 'گزینه غیرفعال شد.')
      await afterSave()
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleBranch = async (item) => {
    try {
      const next = !item.is_active
      await configApi.updateBranch(item.id, { is_active: next })
      setInfo(next ? 'شعبه فعال شد.' : 'شعبه غیرفعال شد.')
      await afterSave()
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleMenu = async (item) => {
    const sectionPk = item.pk ?? item.id
    if (!sectionPk) {
      setError('شناسه بخش منو نامعتبر است.')
      return
    }
    try {
      const next = item.is_active === false
      await configApi.updateMenuSection(sectionPk, { is_active: next })
      setInfo(next ? 'بخش منو نمایش داده می‌شود.' : 'بخش منو مخفی شد.')
      await afterSave()
    } catch (err) {
      setError(err.message)
    }
  }

  if (!isSystemAdmin) {
    return (
      <div className="page">
        <Card title="تنظیمات سیستم">
          <div className="alert-error">فقط مدیر سیستم به تنظیمات دسترسی دارد.</div>
        </Card>
      </div>
    )
  }

  const filteredLookups = lookups.filter((l) => l.category === lookupCategory)

  return (
    <div className="page settings-page">
      {error && <div className="alert-error">{error}</div>}
      {info && <div className="alert-info">{info}</div>}

      <Card title="تنظیمات سیستم">
        <p className="muted" style={{ marginBottom: 16 }}>
          همه تنظیمات در MySQL ذخیره می‌شوند — شعب، گزینه‌های فرم‌ها و منوی پنل.
        </p>
        <div className="branch-tabs settings-tabs">
          <button type="button" className={`branch-tab ${tab === 'branches' ? 'active' : ''}`} onClick={() => setTab('branches')}>شعب</button>
          <button type="button" className={`branch-tab ${tab === 'lookups' ? 'active' : ''}`} onClick={() => setTab('lookups')}>گزینه‌ها</button>
          <button type="button" className={`branch-tab ${tab === 'menu' ? 'active' : ''}`} onClick={() => setTab('menu')}>منوی پنل</button>
          <button type="button" className={`branch-tab ${tab === 'branding' ? 'active' : ''}`} onClick={() => setTab('branding')}>برندینگ</button>
        </div>

        {tab === 'branding' && <LogoSettings onError={setError} onInfo={setInfo} />}

        {loading ? <p className="muted">در حال بارگذاری…</p> : (
          <>
            {tab === 'branches' && (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Button onClick={() => { setSelectedBranch(null); setBranchForm(EMPTY_BRANCH); setBranchModal(true) }}>+ شعبه</Button>
                </div>
                {branches.length === 0 ? <EmptyState message="شعبه‌ای ثبت نشده" /> : (
                  <>
                    <div className="table-wrap settings-table-desktop">
                      <table className="table">
                        <thead><tr><th>کد</th><th>نام</th><th>ترتیب</th><th>وضعیت</th><th>عملیات</th></tr></thead>
                        <tbody>
                          {branches.map((b) => (
                            <tr key={b.id}>
                              <td className="ltr">{b.code}</td>
                              <td><Badge color={b.color}>{b.label}</Badge></td>
                              <td>{b.sort_order}</td>
                              <td>{b.is_active ? 'فعال' : 'غیرفعال'}</td>
                              <td>
                                <button type="button" className="link" onClick={() => { setSelectedBranch(b); setBranchForm({ code: b.code, label: b.label, color: b.color, sort_order: b.sort_order }); setBranchModal(true) }}>ویرایش</button>
                                {' · '}
                                <button type="button" className="link" onClick={() => toggleBranch(b)}>
                                  {b.is_active ? 'غیرفعال' : 'فعال'}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="settings-cards-mobile">
                      {branches.map((b) => (
                        <div key={b.id} className="m-card">
                          <div className="m-card-head">
                            <Badge color={b.color}>{b.label}</Badge>
                            <span className="muted">{b.is_active ? 'فعال' : 'غیرفعال'}</span>
                          </div>
                          <div className="m-card-grid">
                            <div><span className="muted">کد</span><span className="ltr">{b.code}</span></div>
                            <div><span className="muted">ترتیب</span>{b.sort_order}</div>
                          </div>
                          <div className="m-card-actions">
                            <button type="button" className="link" onClick={() => { setSelectedBranch(b); setBranchForm({ code: b.code, label: b.label, color: b.color, sort_order: b.sort_order }); setBranchModal(true) }}>ویرایش</button>
                            <button type="button" className="link" onClick={() => toggleBranch(b)}>{b.is_active ? 'غیرفعال' : 'فعال'}</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}

            {tab === 'lookups' && (
              <>
                <div className="branch-tabs" style={{ marginBottom: 12 }}>
                  {LOOKUP_CATEGORIES.map((c) => (
                    <button key={c.id} type="button" className={`branch-tab ${lookupCategory === c.id ? 'active' : ''}`} onClick={() => setLookupCategory(c.id)}>{c.label}</button>
                  ))}
                </div>
                <Button onClick={() => { setLookupForm({ ...EMPTY_LOOKUP, category: lookupCategory }); setLookupModal(true) }}>+ گزینه</Button>
                <div className="table-wrap settings-table-desktop" style={{ marginTop: 12 }}>
                  <table className="table">
                    <thead><tr><th>کد</th><th>عنوان</th><th>ترتیب</th><th>عملیات</th></tr></thead>
                    <tbody>
                      {filteredLookups.map((l) => (
                        <tr key={l.id}>
                          <td className="ltr">{l.code}</td>
                          <td>{l.label}</td>
                          <td>{l.sort_order}</td>
                          <td>
                            <button type="button" className="link" onClick={() => toggleLookup(l)}>
                              {l.is_active ? 'غیرفعال' : 'فعال'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="settings-cards-mobile" style={{ marginTop: 12 }}>
                  {filteredLookups.map((l) => (
                    <div key={l.id} className="m-card">
                      <div className="m-card-head">
                        <strong>{l.label}</strong>
                        <span className="muted">{l.is_active ? 'فعال' : 'غیرفعال'}</span>
                      </div>
                      <div className="m-card-grid">
                        <div><span className="muted">کد</span><span className="ltr">{l.code}</span></div>
                        <div><span className="muted">ترتیب</span>{l.sort_order}</div>
                      </div>
                      <div className="m-card-actions">
                        <button type="button" className="link" onClick={() => toggleLookup(l)}>{l.is_active ? 'غیرفعال' : 'فعال'}</button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {tab === 'menu' && (
              <>
                {moduleTree?.length > 0 && (
                  <div className="portal-module-matrix" style={{ marginBottom: 16 }}>
                    <p className="muted small">کاتالوگ ماژول (پورتال و زیربخش) — برای نقش‌ها از همین ساختار استفاده می‌شود.</p>
                    {moduleTree.map((portal) => (
                      <div key={portal.id} className="portal-module-block">
                        <div className="portal-module-head">
                          <span className="portal-module-portal-label">{portal.icon} {portal.label}</span>
                          <span className="muted small">{(portal.modules || []).length} زیربخش</span>
                        </div>
                        <div className="portal-module-children menu-section-grid">
                          {(portal.modules || []).map((mod) => (
                            <div key={mod.id} className="menu-section-item">
                              <span>{mod.icon} {mod.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              <div className="table-wrap settings-table-desktop">
                <table className="table">
                  <thead><tr><th>بخش</th><th>صفحه</th><th>ترتیب</th><th>عملیات</th></tr></thead>
                  <tbody>
                    {menuSections.map((m) => (
                      <tr key={m.pk}>
                        <td>{m.icon} {m.label}</td>
                        <td className="ltr">{m.page_key}</td>
                        <td>{m.sort_order}</td>
                        <td>
                          <button type="button" className="link" onClick={() => toggleMenu(m)}>
                            {m.is_active !== false ? 'مخفی' : 'نمایش'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="settings-cards-mobile">
                {menuSections.map((m) => (
                  <div key={m.pk} className="m-card">
                    <div className="m-card-head">
                      <strong>{m.icon} {m.label}</strong>
                      <span className="muted">{m.is_active !== false ? 'نمایش' : 'مخفی'}</span>
                    </div>
                    <div className="m-card-grid">
                      <div><span className="muted">صفحه</span><span className="ltr">{m.page_key}</span></div>
                      <div><span className="muted">ترتیب</span>{m.sort_order}</div>
                    </div>
                    <div className="m-card-actions">
                      <button type="button" className="link" onClick={() => toggleMenu(m)}>{m.is_active !== false ? 'مخفی' : 'نمایش'}</button>
                    </div>
                  </div>
                ))}
              </div>
              </>
            )}
          </>
        )}
      </Card>

      <Modal open={branchModal} onClose={() => setBranchModal(false)} title={selectedBranch ? 'ویرایش شعبه' : 'شعبه جدید'}>
        <form onSubmit={saveBranch} className="form">
          {!selectedBranch && (
            <Field label="کد (انگلیسی)"><input value={branchForm.code} onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value })} required /></Field>
          )}
          <Field label="نام"><input value={branchForm.label} onChange={(e) => setBranchForm({ ...branchForm, label: e.target.value })} required /></Field>
          <Field label="رنگ"><input type="color" value={branchForm.color} onChange={(e) => setBranchForm({ ...branchForm, color: e.target.value })} /></Field>
          <Field label="ترتیب"><input type="number" value={branchForm.sort_order} onChange={(e) => setBranchForm({ ...branchForm, sort_order: Number(e.target.value) })} /></Field>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>

      <Modal open={lookupModal} onClose={() => setLookupModal(false)} title="گزینه جدید">
        <form onSubmit={saveLookup} className="form">
          <Field label="کد"><input value={lookupForm.code} onChange={(e) => setLookupForm({ ...lookupForm, code: e.target.value })} required /></Field>
          <Field label="عنوان"><input value={lookupForm.label} onChange={(e) => setLookupForm({ ...lookupForm, label: e.target.value })} required /></Field>
          <Field label="ترتیب"><input type="number" value={lookupForm.sort_order} onChange={(e) => setLookupForm({ ...lookupForm, sort_order: Number(e.target.value) })} /></Field>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>
    </div>
  )
}
