// صفحه مدیریت مشتریان: فهرست، جستجو، کیف پول، افزودن/ویرایش و تاریخچه.

import { useEffect, useState } from 'react'
import { customersApi, levelsApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import OfficeSectionCard from '../components/OfficeSectionCard'
import { OFFICE_CUSTOMERS_FILTER } from '../config/recordFilterSections'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { PAGE_SIZE } from '../config/pagination'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate, formatMoney } from '../utils/format'
import { todayIso } from '../utils/jalali'
import { hasAnyPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_FORM = { full_name: '', phone: '', email: '', address: '', notes: '', birthday: '' }
const EMPTY_WALLET_FORM = { action: 'deposit', amount: '', description: '' }

export default function Customers({ portal }) {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canEdit = hasAnyPermission(user, ['create_customer', 'edit_customer', 'delete_customer'])

  const [customers, setCustomers] = useState([])
  const [search, setSearch] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [levels, setLevels] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
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

  useRegisterPageGuide(
    portal !== 'office' ? 'customers' : null,
    PAGE_GUIDE_DEFAULTS.customers_shop || '',
  )

  const load = async ({ append = false, offset: nextOffset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const data = await customersApi.list({
        search: search.trim(),
        level_id: levelFilter || undefined,
        is_active: activeFilter,
        offset: nextOffset,
        limit: PAGE_SIZE,
      })
      setCustomers((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))
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
    load()
    levelsApi.list().then((d) => setLevels(d.results || [])).catch(() => setLevels([]))
    customersApi.topBuyers(20, { minPurchases: 2, days: 365 }).then(setTopBuyers).catch(() => setTopBuyers(null))
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
      address: customer.address || '',
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
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (customer) => {
    if (!await confirm({
      title: 'حذف مشتری',
      message: `حذف مشتری «${customer.full_name}»؟`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    await customersApi.remove(customer.id)
    load()
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
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setWalletSaving(false)
    }
  }

  const renderActions = (c) => (
    <div className={fromLegacy("row-actions")}>
      <button type="button" className={fromLegacy("link")} onClick={() => openWallet(c)}>
        کیف پول
      </button>
      <button type="button" className={fromLegacy("link")} onClick={() => openHistory(c)}>
        تاریخچه
      </button>
      {canEdit && (
        <>
          <button type="button" className={fromLegacy("link")} onClick={() => openEdit(c)}>
            ویرایش
          </button>
          <button type="button" className={fromLegacy("link danger")} onClick={() => remove(c)}>
            حذف
          </button>
        </>
      )}
    </div>
  )

  return (
    <div className={fromLegacy("page customers-page")}>
      {topBuyers?.results?.length > 0 && (
        <Card title="مشتریان وفادار — ۱ سال اخیر" className={fromLegacy("top-buyers-card analytics-card")}>
          <div className={fromLegacy("table-wrap")}>
            <table className={fromLegacy("table table-compact")}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>نام</th>
                  <th>موبایل</th>
                  <th>تعداد خرید</th>
                  <th>مجموع خرید (۱ سال)</th>
                </tr>
              </thead>
              <tbody>
                {topBuyers.results.map((c, idx) => (
                  <tr key={c.customer_id}>
                    <td>{idx + 1}</td>
                    <td><strong>{c.full_name}</strong></td>
                    <td className={fromLegacy("ltr")}>{c.phone}</td>
                    <td>{c.purchase_count_year}</td>
                    <td>{formatMoney(c.year_purchases_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {portal === 'office' && (
        <OfficeSectionCard section={OFFICE_CUSTOMERS_FILTER} />
      )}

      {portal !== 'office' && (
      <Card
        title="فهرست مشتریان"
        actions={canEdit ? <Button onClick={openCreate}>+ مشتری جدید</Button> : null}
      >
        <FilterBar className={fromLegacy("page-filters--toolbar")}>
          <Field label="جستجو">
            <input
              className={fromLegacy("search-input")}
              placeholder="جستجو بر اساس نام، موبایل یا کد باشگاه…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </Field>
          <Field label="سطح باشگاه">
            <Select
              value={levelFilter}
              onChange={setLevelFilter}
              options={[
                { value: '', label: 'همه سطوح' },
                ...levels.map((lv) => ({ value: String(lv.id), label: lv.name })),
              ]}
              placeholder="همه سطوح"
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
          <div className={fromLegacy("page-filters-actions")}>
            <Button variant="ghost" type="button" onClick={() => load()}>اعمال فیلتر</Button>
          </div>
        </FilterBar>
        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        {loading ? (
          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
        ) : customers.length === 0 ? (
          <EmptyState text="مشتری‌ای یافت نشد." />
        ) : (
          <>
            <div className={fromLegacy("table-wrap customers-table-desktop")}>
              <table className={fromLegacy("table")}>
                <thead>
                  <tr>
                    <th>نام</th>
                    <th>موبایل</th>
                    <th>آدرس</th>
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
                      <td className={fromLegacy("ltr")}>{c.phone}</td>
                      <td className={fromLegacy("customer-address-cell")}>{c.address || '—'}</td>
                      <td className={fromLegacy("ltr")}>{c.membership_code || '—'}</td>
                      <td>{c.level ? <Badge color={c.level.color}>{c.level.name}</Badge> : '—'}</td>
                      <td>
                        <button type="button" className={fromLegacy("link wallet-balance-link")} onClick={() => openWallet(c)}>
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

            <div className={fromLegacy("customers-cards-mobile")}>
              {customers.map((c) => (
                <div key={c.id} className={fromLegacy("customer-card")}>
                  <div className={fromLegacy("customer-card-head")}>
                    <div>
                      <strong>{c.full_name}</strong>
                      <span className={fromLegacy("ltr muted")}> — {c.phone}</span>
                    </div>
                    {c.level ? <Badge color={c.level.color}>{c.level.name}</Badge> : null}
                  </div>
                  <div className={fromLegacy("customer-card-stats")}>
                    <div>
                      <span className={fromLegacy("muted")}>کیف پول</span>
                      <button type="button" className={fromLegacy("link wallet-balance-link")} onClick={() => openWallet(c)}>
                        {formatMoney(c.wallet_balance || 0)}
                      </button>
                    </div>
                    <div>
                      <span className={fromLegacy("muted")}>مجموع خرید</span>
                      <strong>{formatMoney(c.total_purchases)}</strong>
                    </div>
                    <div>
                      <span className={fromLegacy("muted")}>آخرین خرید</span>
                      <span>{c.last_purchase_at ? formatDate(c.last_purchase_at) : '—'}</span>
                    </div>
                    {c.address && (
                      <div className={fromLegacy("customer-card-address")}>
                        <span className={fromLegacy("muted")}>آدرس</span>
                        <span>{c.address}</span>
                      </div>
                    )}
                  </div>
                  {renderActions(c)}
                </div>
              ))}
            </div>
            <LoadMoreButton
              hasMore={customers.length < total}
              loading={loadingMore}
              onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
            />
          </>
        )}
      </Card>
      )}

      <Modal title={editing ? 'ویرایش مشتری' : 'مشتری جدید'} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className={fromLegacy("form")}>
          <Field label="نام کامل">
            <input value={form.full_name} onChange={update('full_name')} required />
          </Field>
          <Field label="موبایل">
            <input className={fromLegacy("ltr")} value={form.phone} onChange={update('phone')} required />
          </Field>
          <Field label="آدرس">
            <textarea value={form.address} onChange={update('address')} rows={2} placeholder="آدرس منزل یا محل تحویل" />
          </Field>
          <Field label="ایمیل">
            <input className={fromLegacy("ltr")} value={form.email} onChange={update('email')} />
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
                  className={fromLegacy("link")}
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
          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
        ) : (
          <div className={fromLegacy("wallet-panel")}>
            <div className={fromLegacy("wallet-balance-banner")}>
              <span className={fromLegacy("muted")}>موجودی فعلی</span>
              <strong>{formatMoney(walletData.balance)}</strong>
            </div>

            {walletInfo && <div className={fromLegacy("alert-info")}>{walletInfo}</div>}

            <form onSubmit={submitWallet} className={fromLegacy("form wallet-form")}>
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
              <Field label="مبلغ (ریال)">
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

            <h4 className={fromLegacy("wallet-tx-title")}>تراکنش‌های اخیر</h4>
            {walletData.transactions.length === 0 ? (
              <EmptyState text="تراکنشی ثبت نشده." />
            ) : (
              <>
                <div className={fromLegacy("table-wrap wallet-table-desktop")}>
                  <table className={fromLegacy("table")}>
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
                <div className={fromLegacy("wallet-cards-mobile")}>
                  {walletData.transactions.map((tx) => (
                    <div key={tx.id} className={fromLegacy("wallet-tx-card")}>
                      <div className={fromLegacy("wallet-tx-card-head")}>
                        <Badge color={tx.amount >= 0 ? 'var(--success)' : 'var(--danger)'}>
                          {tx.transaction_type_display}
                        </Badge>
                        <span className={tx.amount >= 0 ? 'wallet-plus' : 'wallet-minus'}>
                          {tx.amount >= 0 ? '+' : ''}
                          {formatMoney(tx.amount)}
                        </span>
                      </div>
                      <p className={fromLegacy("muted")}>{tx.description || 'بدون شرح'}</p>
                      <div className={fromLegacy("wallet-tx-card-meta")}>
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
        title={historyFor ? `تاریخچه خرید: ${historyFor.full_name}` : ''}
        open={!!historyFor}
        onClose={() => setHistoryFor(null)}
        wide
      >
        {!history ? (
          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
        ) : (
          <div className={fromLegacy("history purchase-history")}>
            <h4>فروش‌ها و محصولات</h4>
            {history.sales.length === 0 ? (
              <EmptyState text="فروشی ثبت نشده." />
            ) : (
              <div className={fromLegacy("purchase-history-list")}>
                {history.sales.map((s) => (
                  <article key={s.id} className={fromLegacy("purchase-history-sale")}>
                    <div className={fromLegacy("purchase-history-sale-head")}>
                      <div>
                        <strong>فاکتور {s.invoice_number || s.id}</strong>
                        <span className={fromLegacy("muted small")}> — {formatDate(s.sold_at)}</span>
                      </div>
                      <div className={fromLegacy("purchase-history-sale-totals")}>
                        <span>{formatMoney(s.final_amount)}</span>
                        <Badge color={s.payment_status === 'paid' ? 'var(--success)' : 'var(--warning)'}>
                          {s.payment_status_display}
                        </Badge>
                      </div>
                    </div>
                    {s.line_items?.length ? (
                      <div className={fromLegacy("table-wrap")}>
                        <table className={fromLegacy("table purchase-history-items")}>
                          <thead>
                            <tr>
                              <th>محصول</th>
                              <th>مدل</th>
                              <th>پارچه</th>
                              <th>رنگ</th>
                              <th>تعداد</th>
                              <th>قیمت واحد</th>
                              <th>جمع</th>
                            </tr>
                          </thead>
                          <tbody>
                            {s.line_items.map((item) => (
                              <tr key={item.id}>
                                <td>{item.product_name}</td>
                                <td>{item.product_model || '—'}</td>
                                <td>{item.fabric || '—'}</td>
                                <td>
                                  {item.color_name ? (
                                    <span className={fromLegacy("history-color-cell")}>
                                      {item.color_hex && (
                                        <span className={fromLegacy("color-swatch small")} style={{ background: item.color_hex }} />
                                      )}
                                      {item.color_name}
                                    </span>
                                  ) : '—'}
                                </td>
                                <td>{item.quantity}</td>
                                <td>{formatMoney(item.unit_price)}</td>
                                <td>{formatMoney(item.line_total)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className={fromLegacy("muted small")}>جزئیات محصول ثبت نشده.</p>
                    )}
                  </article>
                ))}
              </div>
            )}
            <h4>تاریخچه تغییر سطح</h4>
            {history.level_history.length === 0 ? (
              <EmptyState text="تغییر سطحی ثبت نشده." />
            ) : (
              <div className={fromLegacy("table-wrap")}>
                <table className={fromLegacy("table")}>
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
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
