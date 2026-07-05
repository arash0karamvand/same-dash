// صفحه مدیریت مشتریان: فهرست، جستجو، کیف پول، افزودن/ویرایش و تاریخچه.

import { useEffect, useState } from 'react'
import { customersApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { formatDate, formatMoney } from '../utils/format'
import { todayIso } from '../utils/jalali'
import { hasAnyPermission } from '../utils/permissions'

const EMPTY_FORM = { full_name: '', phone: '', email: '', notes: '', birthday: '' }
const EMPTY_WALLET_FORM = { action: 'deposit', amount: '', description: '' }

export default function Customers() {
  const { user } = useAuth()
  const canEdit = hasAnyPermission(user, ['create_customer', 'edit_customer', 'delete_customer'])

  const [customers, setCustomers] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [walletInfo, setWalletInfo] = useState('')

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)

  const [historyFor, setHistoryFor] = useState(null)
  const [history, setHistory] = useState(null)

  const [walletFor, setWalletFor] = useState(null)
  const [walletData, setWalletData] = useState(null)
  const [walletForm, setWalletForm] = useState(EMPTY_WALLET_FORM)
  const [walletSaving, setWalletSaving] = useState(false)
  const [topBuyers, setTopBuyers] = useState(null)

  const load = async (searchValue = '') => {
    setLoading(true)
    try {
      const data = await customersApi.list(searchValue)
      setCustomers(data.results)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    customersApi.topBuyers(5).then(setTopBuyers).catch(() => setTopBuyers(null))
  }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setModalOpen(true)
  }

  const openEdit = (customer) => {
    setEditing(customer)
    setForm({
      full_name: customer.full_name,
      phone: customer.phone,
      email: customer.email,
      notes: customer.notes,
      birthday: customer.birthday?.slice(0, 10) || '',
    })
    setModalOpen(true)
  }

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const save = async (e) => {
    e.preventDefault()
    try {
      if (editing) {
        await customersApi.update(editing.id, form)
      } else {
        await customersApi.create(form)
      }
      setModalOpen(false)
      load(search)
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (customer) => {
    if (!confirm(`حذف مشتری «${customer.full_name}»؟`)) return
    await customersApi.remove(customer.id)
    load(search)
  }

  const openHistory = async (customer) => {
    setHistoryFor(customer)
    setHistory(null)
    const data = await customersApi.history(customer.id)
    setHistory(data)
  }

  const openWallet = async (customer) => {
    setWalletFor(customer)
    setWalletData(null)
    setWalletForm(EMPTY_WALLET_FORM)
    setWalletInfo('')
    setError('')
    try {
      const data = await customersApi.wallet(customer.id)
      setWalletData(data)
    } catch (e) {
      setError(e.message)
    }
  }

  const submitWallet = async (e) => {
    e.preventDefault()
    if (!walletFor) return
    setWalletSaving(true)
    setWalletInfo('')
    setError('')
    try {
      const data = await customersApi.walletAdjust(walletFor.id, {
        action: walletForm.action,
        amount: Number(walletForm.amount),
        description: walletForm.description,
      })
      setWalletData(data)
      setWalletForm(EMPTY_WALLET_FORM)
      setWalletInfo('تراکنش با موفقیت ثبت شد.')
      load(search)
    } catch (err) {
      setError(err.message)
    } finally {
      setWalletSaving(false)
    }
  }

  const renderActions = (c) => (
    <div className="row-actions">
      <button type="button" className="link" onClick={() => openWallet(c)}>
        کیف پول
      </button>
      <button type="button" className="link" onClick={() => openHistory(c)}>
        تاریخچه
      </button>
      {canEdit && (
        <>
          <button type="button" className="link" onClick={() => openEdit(c)}>
            ویرایش
          </button>
          <button type="button" className="link danger" onClick={() => remove(c)}>
            حذف
          </button>
        </>
      )}
    </div>
  )

  return (
    <div className="page customers-page">
      {topBuyers?.top && (
        <Card title="بیشترین خرید" className="top-buyers-card">
          <div className="top-buyer-hero">
            <div>
              <strong>{topBuyers.top.full_name}</strong>
              <p className="muted small">{topBuyers.top.phone}</p>
            </div>
            <div className="top-buyer-amount">
              <span className="muted small">مجموع خرید</span>
              <strong>{formatMoney(topBuyers.top.total_purchases)}</strong>
            </div>
          </div>
          {topBuyers.results?.length > 1 && (
            <ul className="top-buyers-list">
              {topBuyers.results.slice(1).map((c, idx) => (
                <li key={c.id}>
                  <span>{idx + 2}. {c.full_name}</span>
                  <span>{formatMoney(c.total_purchases)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card
        title="فهرست مشتریان"
        actions={canEdit ? <Button onClick={openCreate}>+ مشتری جدید</Button> : null}
      >
        <FilterBar className="page-filters--toolbar">
          <Field label="جستجو">
            <input
              className="search-input"
              placeholder="جستجو بر اساس نام یا موبایل…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load(search)}
            />
          </Field>
          <div className="page-filters-actions">
            <Button variant="ghost" type="button" onClick={() => load(search)}>جستجو</Button>
          </div>
        </FilterBar>
        {error && <div className="alert-error">{error}</div>}
        {loading ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : customers.length === 0 ? (
          <EmptyState text="مشتری‌ای یافت نشد." />
        ) : (
          <>
            <div className="table-wrap customers-table-desktop">
              <table className="table">
                <thead>
                  <tr>
                    <th>نام</th>
                    <th>موبایل</th>
                    <th>کد باشگاه</th>
                    <th>سطح</th>
                    <th>کیف پول</th>
                    <th>مجموع خرید</th>
                    <th>آخرین خرید</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((c) => (
                    <tr key={c.id}>
                      <td>{c.full_name}</td>
                      <td className="ltr">{c.phone}</td>
                      <td className="ltr">{c.membership_code || '—'}</td>
                      <td>{c.level ? <Badge color={c.level.color}>{c.level.name}</Badge> : '—'}</td>
                      <td>
                        <button type="button" className="link wallet-balance-link" onClick={() => openWallet(c)}>
                          {formatMoney(c.wallet_balance || 0)}
                        </button>
                      </td>
                      <td>{formatMoney(c.total_purchases)}</td>
                      <td>{c.last_purchase_at ? formatDate(c.last_purchase_at) : '—'}</td>
                      <td>{renderActions(c)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="customers-cards-mobile">
              {customers.map((c) => (
                <div key={c.id} className="customer-card">
                  <div className="customer-card-head">
                    <div>
                      <strong>{c.full_name}</strong>
                      <span className="ltr muted"> — {c.phone}</span>
                    </div>
                    {c.level ? <Badge color={c.level.color}>{c.level.name}</Badge> : null}
                  </div>
                  <div className="customer-card-stats">
                    <div>
                      <span className="muted">کیف پول</span>
                      <button type="button" className="link wallet-balance-link" onClick={() => openWallet(c)}>
                        {formatMoney(c.wallet_balance || 0)}
                      </button>
                    </div>
                    <div>
                      <span className="muted">مجموع خرید</span>
                      <strong>{formatMoney(c.total_purchases)}</strong>
                    </div>
                    <div>
                      <span className="muted">آخرین خرید</span>
                      <span>{c.last_purchase_at ? formatDate(c.last_purchase_at) : '—'}</span>
                    </div>
                  </div>
                  {renderActions(c)}
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      <Modal title={editing ? 'ویرایش مشتری' : 'مشتری جدید'} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className="form">
          <Field label="نام کامل">
            <input value={form.full_name} onChange={update('full_name')} required />
          </Field>
          <Field label="موبایل">
            <input className="ltr" value={form.phone} onChange={update('phone')} required />
          </Field>
          <Field label="ایمیل">
            <input className="ltr" value={form.email} onChange={update('email')} />
          </Field>
          <Field label="یادداشت">
            <textarea value={form.notes} onChange={update('notes')} rows={3} />
          </Field>
          <Field label="تاریخ تولد (اختیاری)">
            {form.birthday ? (
              <>
                <PersianDateInput
                  value={form.birthday}
                  onChange={(v) => setForm({ ...form, birthday: v })}
                  minYear={1300}
                  placeholder="تاریخ تولد را انتخاب کنید"
                />
                <button
                  type="button"
                  className="link"
                  style={{ marginTop: 6 }}
                  onClick={() => setForm({ ...form, birthday: '' })}
                >
                  پاک کردن تاریخ تولد
                </button>
              </>
            ) : (
              <Button type="button" variant="ghost" onClick={() => setForm({ ...form, birthday: todayIso() })}>
                + افزودن تاریخ تولد
              </Button>
            )}
          </Field>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>

      <Modal
        title={walletFor ? `کیف پول: ${walletFor.full_name}` : ''}
        open={!!walletFor}
        onClose={() => setWalletFor(null)}
      >
        {!walletData ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : (
          <div className="wallet-panel">
            <div className="wallet-balance-banner">
              <span className="muted">موجودی فعلی</span>
              <strong>{formatMoney(walletData.balance)}</strong>
            </div>

            {walletInfo && <div className="alert-info">{walletInfo}</div>}

            <form onSubmit={submitWallet} className="form wallet-form">
              <Field label="نوع تراکنش">
                <Select
                  value={walletForm.action}
                  onChange={(v) => setWalletForm({ ...walletForm, action: v })}
                  options={[
                    { value: 'deposit', label: 'واریز (افزایش)' },
                    { value: 'withdraw', label: 'برداشت (کاهش)' },
                  ]}
                />
              </Field>
              <Field label="مبلغ (تومان)">
                <MoneyInput
                  min="1"
                  value={walletForm.amount}
                  onChange={(e) => setWalletForm({ ...walletForm, amount: e.target.value })}
                  required
                />
              </Field>
              <Field label="شرح (اختیاری)">
                <input
                  value={walletForm.description}
                  onChange={(e) => setWalletForm({ ...walletForm, description: e.target.value })}
                  placeholder="مثلاً هدیه، بازگشت وجه، …"
                />
              </Field>
              <Button type="submit" disabled={walletSaving}>
                {walletSaving ? 'در حال ثبت…' : 'ثبت تراکنش'}
              </Button>
            </form>

            <h4 className="wallet-tx-title">تراکنش‌های اخیر</h4>
            {walletData.transactions.length === 0 ? (
              <EmptyState text="تراکنشی ثبت نشده." />
            ) : (
              <>
                <div className="table-wrap wallet-table-desktop">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>نوع</th>
                        <th>مبلغ</th>
                        <th>موجودی بعد</th>
                        <th>شرح</th>
                        <th>ثبت‌کننده</th>
                        <th>تاریخ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {walletData.transactions.map((tx) => (
                        <tr key={tx.id}>
                          <td>{tx.transaction_type_display}</td>
                          <td className={tx.amount >= 0 ? 'wallet-plus' : 'wallet-minus'}>
                            {tx.amount >= 0 ? '+' : ''}
                            {formatMoney(tx.amount)}
                          </td>
                          <td>{formatMoney(tx.balance_after)}</td>
                          <td>{tx.description || '—'}</td>
                          <td>{tx.recorded_by || '—'}</td>
                          <td>{formatDate(tx.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="wallet-cards-mobile">
                  {walletData.transactions.map((tx) => (
                    <div key={tx.id} className="wallet-tx-card">
                      <div className="wallet-tx-card-head">
                        <Badge color={tx.amount >= 0 ? '#10b981' : '#ef4444'}>
                          {tx.transaction_type_display}
                        </Badge>
                        <span className={tx.amount >= 0 ? 'wallet-plus' : 'wallet-minus'}>
                          {tx.amount >= 0 ? '+' : ''}
                          {formatMoney(tx.amount)}
                        </span>
                      </div>
                      <p className="muted">{tx.description || 'بدون شرح'}</p>
                      <div className="wallet-tx-card-meta">
                        <span>موجودی: {formatMoney(tx.balance_after)}</span>
                        <span>{formatDate(tx.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </Modal>

      <Modal
        title={historyFor ? `تاریخچه: ${historyFor.full_name}` : ''}
        open={!!historyFor}
        onClose={() => setHistoryFor(null)}
      >
        {!history ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : (
          <div className="history">
            <h4>فروش‌ها</h4>
            {history.sales.length === 0 ? (
              <EmptyState text="فروشی ثبت نشده." />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>مبلغ نهایی</th>
                    <th>روش پرداخت</th>
                    <th>تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {history.sales.map((s) => (
                    <tr key={s.id}>
                      <td>{formatMoney(s.final_amount)}</td>
                      <td>{s.payment_method_display}</td>
                      <td>{formatDate(s.sold_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <h4>تاریخچه تغییر سطح</h4>
            {history.level_history.length === 0 ? (
              <EmptyState text="تغییر سطحی ثبت نشده." />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>سطح قبلی</th>
                    <th>سطح جدید</th>
                    <th>مجموع خرید</th>
                    <th>تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {history.level_history.map((h) => (
                    <tr key={h.id}>
                      <td>{h.previous_level || '—'}</td>
                      <td>{h.new_level || '—'}</td>
                      <td>{formatMoney(h.total_purchases_at_change)}</td>
                      <td>{formatDate(h.changed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
