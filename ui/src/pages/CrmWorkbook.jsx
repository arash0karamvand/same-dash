// CRM 1405 — همان تب‌ها و ستون‌های فایل اکسل؛ ورود از اکسل یا دستی/فروش

import { useCallback, useEffect, useMemo, useState } from 'react'
import { crmWorkbookApi } from '../api/client'
import { Badge, Button, Card, EmptyState, Field, LoadMoreButton } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

function formatCell(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1_000_000) return formatMoney(value)
    return toPersianDigits(String(value))
  }
  return String(value)
}

function isMoneyColumn(col) {
  return /مبلغ|مانده|تخفیف|کرایه|واریز|کسر|بستانکار|نهایی/.test(col)
}

export default function CrmWorkbook() {
  const [schema, setSchema] = useState(null)
  const [activeTab, setActiveTab] = useState('customers')
  const [rows, setRows] = useState([])
  const [columns, setColumns] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [importOpen, setImportOpen] = useState(false)
  const [password, setPassword] = useState('1999')
  const [importing, setImporting] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const [editRow, setEditRow] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)

  const tabLabel = useMemo(() => {
    const t = schema?.tabs?.find((x) => x.key === activeTab)
    return t?.label || activeTab
  }, [schema, activeTab])

  const loadSchema = useCallback(async () => {
    const data = await crmWorkbookApi.schema()
    setSchema(data)
    if (data?.tabs?.length && !data.tabs.some((t) => t.key === activeTab)) {
      setActiveTab(data.tabs[0].key)
    }
  }, [activeTab])

  const loadRows = useCallback(
    async ({ append = false, nextOffset = 0 } = {}) => {
      if (append) setLoadingMore(true)
      else setLoading(true)
      setError('')
      try {
        const data = await crmWorkbookApi.list(activeTab, {
          search: search.trim(),
          offset: nextOffset,
          limit: PAGE_SIZE,
        })
        setColumns(data.columns || [])
        setTotal(data.total || 0)
        setOffset(nextOffset + (data.results?.length || 0))
        setRows((prev) => (append ? [...prev, ...(data.results || [])] : data.results || []))
      } catch (e) {
        setError(e.message || 'خطا در بارگذاری')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [activeTab, search],
  )

  useEffect(() => {
    loadSchema().catch((e) => setError(e.message))
  }, [loadSchema])

  useEffect(() => {
    loadRows({ append: false, nextOffset: 0 })
  }, [loadRows])

  const onImport = async (file) => {
    if (!file) return
    setImporting(true)
    setNotice('')
    setError('')
    try {
      const stats = await crmWorkbookApi.importFile(file, { password, replace: true })
      setNotice(`وارد شد: ${toPersianDigits(stats.total_rows || 0)} ردیف`)
      setImportOpen(false)
      await loadRows({ append: false, nextOffset: 0 })
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }

  const onSyncSales = async () => {
    setSyncing(true)
    setNotice('')
    setError('')
    try {
      const stats = await crmWorkbookApi.syncSales()
      setNotice(
        `همگام‌سازی فروش: ${toPersianDigits(stats.created || 0)} جدید، ${toPersianDigits(stats.updated || 0)} به‌روز`,
      )
      if (activeTab === 'customers') await loadRows({ append: false, nextOffset: 0 })
    } catch (e) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  const openNew = () => {
    const blank = Object.fromEntries((columns || []).map((c) => [c, '']))
    setEditRow(null)
    setEditForm(blank)
  }

  const openEdit = (row) => {
    setEditRow(row)
    setEditForm({ ...(row.data || {}) })
  }

  const saveRow = async () => {
    setSaving(true)
    setError('')
    try {
      await crmWorkbookApi.upsert(activeTab, { id: editRow?.id, data: editForm })
      setEditRow(undefined)
      setEditForm({})
      await loadRows({ append: false, nextOffset: 0 })
      setNotice('ذخیره شد')
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const exportFile = () => {
    window.location.href = crmWorkbookApi.exportUrl()
  }

  return (
    <div className={fromLegacy('page crm-workbook-page')}>
      <div className={fromLegacy('page-header')}>
        <div>
          <h1>CRM 1405</h1>
          <p className={fromLegacy('muted')}>
            همان تب‌ها و پارامترهای فایل اکسل — داده از اکسل (رمز 1999) یا ثبت/فروش در سایت
          </p>
        </div>
        <div className={fromLegacy('page-header-actions')}>
          <Button variant="secondary" onClick={() => setImportOpen(true)}>
            ورود از اکسل
          </Button>
          <Button variant="secondary" onClick={onSyncSales} disabled={syncing}>
            {syncing ? '…' : 'همگام تب مشتریان از فروش'}
          </Button>
          <Button variant="secondary" onClick={exportFile}>
            خروجی اکسل
          </Button>
          <Button onClick={openNew}>ردیف جدید</Button>
        </div>
      </div>

      {notice && <div className={fromLegacy('alert-success')}>{notice}</div>}
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}

      <div className={fromLegacy('crm-workbook-tabs')}>
        {(schema?.tabs || []).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={fromLegacy(activeTab === tab.key ? 'crm-tab active' : 'crm-tab')}
            onClick={() => {
              setActiveTab(tab.key)
              setOffset(0)
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Card>
        <div className={fromLegacy('filter-bar')}>
          <Field label="جستجو (فاکتور / نام)">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadRows({ append: false, nextOffset: 0 })}
            />
          </Field>
          <Button variant="secondary" onClick={() => loadRows({ append: false, nextOffset: 0 })}>
            اعمال
          </Button>
          <span className={fromLegacy('muted')}>
            {tabLabel} — {toPersianDigits(total)} ردیف
          </span>
        </div>

        {loading && !rows.length ? (
          <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
        ) : !rows.length ? (
          <EmptyState title="ردیفی نیست" hint="فایل CRM 1405 را import کنید یا ردیف دستی بسازید." />
        ) : (
          <div className={fromLegacy('table-wrap crm-workbook-table-wrap')}>
            <table className={fromLegacy('table table-compact')}>
              <thead>
                <tr>
                  <th>عملیات</th>
                  {columns.map((c) => (
                    <th key={c}>{c.trim()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
                        ویرایش
                      </Button>
                      {row.source && <Badge>{row.source}</Badge>}
                    </td>
                    {columns.map((c) => (
                      <td key={c} className={isMoneyColumn(c) ? fromLegacy('is-number') : ''}>
                        {formatCell(row.data?.[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {rows.length < total && (
          <LoadMoreButton loading={loadingMore} onClick={() => loadRows({ append: true, nextOffset: offset })} />
        )}
      </Card>

      {importOpen && (
        <div className={fromLegacy('modal-backdrop')} role="presentation" onClick={() => !importing && setImportOpen(false)}>
          <div className={fromLegacy('modal')} onClick={(e) => e.stopPropagation()}>
            <h2>ورود فایل CRM</h2>
            <p className={fromLegacy('muted')}>فرمت .xlsb (CRM 1405) یا .xlsx — تب‌های موجود جایگزین می‌شوند.</p>
            <Field label="رمز فایل">
              <input value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Field label="فایل">
              <input
                type="file"
                accept=".xlsb,.xlsx"
                disabled={importing}
                onChange={(e) => onImport(e.target.files?.[0])}
              />
            </Field>
            {importing && <p className={fromLegacy('muted')}>در حال خواندن…</p>}
            <Button variant="ghost" onClick={() => setImportOpen(false)} disabled={importing}>
              بستن
            </Button>
          </div>
        </div>
      )}

      {editForm && Object.keys(editForm).length > 0 && (
        <div className={fromLegacy('modal-backdrop')} role="presentation" onClick={() => !saving && setEditForm({})}>
          <div className={fromLegacy('modal modal-wide')} onClick={(e) => e.stopPropagation()}>
            <h2>{editRow ? 'ویرایش ردیف' : 'ردیف جدید'} — {tabLabel}</h2>
            <div className={fromLegacy('form-grid crm-edit-grid')}>
              {columns.map((c) => (
                <Field key={c} label={c.trim()}>
                  <input
                    value={editForm[c] ?? ''}
                    onChange={(e) => setEditForm({ ...editForm, [c]: e.target.value })}
                  />
                </Field>
              ))}
            </div>
            <div className={fromLegacy('modal-actions')}>
              <Button variant="ghost" onClick={() => setEditForm({})} disabled={saving}>
                انصراف
              </Button>
              <Button onClick={saveRow} disabled={saving}>
                {saving ? '…' : 'ذخیره'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
