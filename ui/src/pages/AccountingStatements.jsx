import { useCallback, useEffect, useState } from 'react'
import { accountingApi } from '../api/client'
import {
  AccountingDataPanel,
  AccountingPageHeader,
  AccountingSummary,
  AccountingToolbar,
} from '../components/accounting/AccountingERP'
import PersianDateInput from '../components/PersianDateInput'
import { Button, EmptyState } from '../components/ui'
import LiveTBalance from '../components/accounting/LiveTBalance'
import { formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

function money(value) {
  return formatRial(value || 0)
}

function ratioText(value) {
  if (value == null) return '—'
  return Number(value).toLocaleString('fa-IR', { maximumFractionDigits: 2 })
}

function StatementTable({ rows, totalLabel, total, tone = 'debit' }) {
  if (!rows.length) return <EmptyState text="مانده‌ای در این بخش نیست." />
  const amountClass = tone === 'credit' ? 'acct-credit' : 'acct-debit'
  return (
    <div className="acct-card-stack is-compact">
      <div className="acct-strip-head acct-strip-head--3" aria-hidden>
        <span>کد</span>
        <span>حساب</span>
        <span className="is-num">مانده</span>
      </div>
      {rows.map((row) => (
        <div key={row.account_id} className="acct-strip acct-strip--3">
          <span className="acct-number">{row.code}</span>
          <span>{row.name}</span>
          <strong className={`acct-number ${amountClass}`}>{money(row.balance)}</strong>
        </div>
      ))}
      <div className="acct-strip acct-strip--3">
        <span />
        <strong>{totalLabel}</strong>
        <strong className={`acct-number ${amountClass}`}>{money(total)}</strong>
      </div>
    </div>
  )
}

function FlowTable({ rows, total }) {
  return (
    <div className="acct-card-stack is-compact">
      {rows.map((row) => (
        <div key={row.label} className="acct-strip acct-strip--2">
          <span>{row.label}</span>
          <strong className={`acct-number ${(row.amount || 0) < 0 ? 'acct-debit' : 'acct-credit'}`}>{money(row.amount)}</strong>
        </div>
      ))}
      <div className="acct-strip acct-strip--2">
        <strong>جمع</strong>
        <strong className="acct-number">{money(total)}</strong>
      </div>
    </div>
  )
}

export default function AccountingStatements() {
  const api = accountingApi
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [books, setBooks] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setBooks(await api.books({ dateFrom, dateTo }))
    } catch (err) {
      setBooks(null)
      setError(err.message || 'صورت‌ها بارگذاری نشد.')
    } finally {
      setLoading(false)
    }
  }, [api, dateFrom, dateTo])

  useEffect(() => {
    const timer = setTimeout(load, 0)
    return () => clearTimeout(timer)
  }, [load])

  const downloadBeancount = async () => {
    setError('')
    try {
      const response = await fetch(api.booksBeancountPath({ dateFrom, dateTo }), { credentials: 'include' })
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new Error(payload?.error || 'خروجی Beancount ساخته نشد.')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'accounting.beancount'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message || 'خروجی Beancount ساخته نشد.')
    }
  }

  const closeBooks = async () => {
    setError('')
    setNotice('')
    try {
      const created = await api.closeBooks({ date_from: dateFrom, date_to: dateTo })
      setNotice(`پیش‌نویس بستن حساب‌ها با شماره ${created.document_code} در مدیریت اسناد است. تا تایید، در دفاتر اثر ندارد.`)
    } catch (err) {
      setError(err.message || 'بستن حساب‌ها انجام نشد.')
    }
  }

  const push = async (target) => {
    setError('')
    setNotice('')
    try {
      const result = await api.pushBooks({ target, date_from: dateFrom, date_to: dateTo })
      setNotice(`${result.count.toLocaleString('fa-IR')} سند به ${target === 'odoo' ? 'Odoo' : 'ERPNext'} ارسال شد.`)
    } catch (err) {
      setError(err.message || 'ارسال انجام نشد.')
    }
  }

  const sheet = books?.balance_sheet
  const income = books?.income_statement
  const flow = books?.cash_flow
  
  // وضعیت اتصال سیستم‌های خارجی
  const odooReady = books?.odoo?.configured || false
  const erpnextReady = books?.erpnext?.configured || false
  const beancountValid = books?.beancount?.valid || false

  return (
    <div className={fromLegacy('acct-erp-page')}>
      <AccountingPageHeader
        eyebrow="دفتر یکپارچه"
        title="صورت‌های مالی"
        description="ترازنامه، سود و زیان و جریان نقد از اسناد قطعی همین دفتر. خروجی Beancount و سند Odoo و ERPNext از همین گردش ساخته می‌شود."
      />
      <AccountingToolbar>
        <PersianDateInput value={dateFrom} onChange={setDateFrom} placeholder="از تاریخ" />
        <PersianDateInput value={dateTo} onChange={setDateTo} placeholder="تا تاریخ" />
        <Button type="button" onClick={load} disabled={loading}>
          {loading ? 'در حال محاسبه...' : 'نمایش'}
        </Button>
        <Button 
          type="button" 
          variant="ghost" 
          onClick={downloadBeancount}
          disabled={!beancountValid}
          title={beancountValid ? 'دانلود فایل Beancount' : 'فایل Beancount معتبر نیست'}
        >
          دانلود Beancount
        </Button>
        <Button 
          type="button" 
          variant="ghost" 
          onClick={closeBooks}
          disabled={loading || !books}
        >
          بستن حساب‌های موقت
        </Button>
        <Button 
          type="button" 
          variant="ghost" 
          onClick={() => push('odoo')}
          disabled={!odooReady}
          title={odooReady ? 'ارسال اسناد به Odoo' : 'اتصال Odoo تنظیم نشده است'}
        >
          ارسال به Odoo
        </Button>
        <Button 
          type="button" 
          variant="ghost" 
          onClick={() => push('erpnext')}
          disabled={!erpnextReady}
          title={erpnextReady ? 'ارسال اسناد به ERPNext' : 'اتصال ERPNext تنظیم نشده است'}
        >
          ارسال به ERPNext
        </Button>
      </AccountingToolbar>
      {error && (
        <div style={{
          padding: '1rem',
          background: 'var(--danger-soft)',
          color: 'var(--danger)',
          borderRadius: '0.5rem',
          marginBottom: '1rem',
        }}>
          {error}
        </div>
      )}
      {notice && (
        <div style={{
          padding: '1rem',
          background: 'var(--success-soft)',
          color: 'var(--success)',
          borderRadius: '0.5rem',
          marginBottom: '1rem',
        }}>
          {notice}
        </div>
      )}
      {books && sheet && income && flow && (
        <>
          <AccountingSummary
            items={[
              { label: 'دارایی', value: money(sheet.asset_total) },
              { label: 'بدهی و سرمایه', value: money(sheet.liabilities_and_equity), tone: sheet.balanced ? 'ok' : 'danger' },
              { label: 'سود دوره', value: money(income.net_income) },
              { label: 'تغییر نقد', value: money(flow.cash_change), tone: flow.reconciled ? 'ok' : 'danger' },
            ]}
          />
          <AccountingDataPanel title="موتورها و اتصال‌های خارجی" subtitle="هر کتابخانه روی همین اسناد کار می‌کند.">
            <div style={{ display: 'grid', gap: '1rem' }}>
              {books.engines.map((engine) => (
                <div key={engine.id} style={{
                  padding: '0.75rem',
                  background: engine.active ? 'var(--success-soft)' : 'var(--warning-soft)',
                  borderRadius: '0.375rem',
                  borderRight: `3px solid ${engine.active ? 'var(--success)' : 'var(--warning)'}`,
                }}>
                  <strong>{engine.label}</strong>
                  {' — '}
                  <span style={{ color: engine.active ? 'var(--success)' : 'var(--warning)' }}>
                    {engine.active ? '✓ فعال' : '○ منتظر اتصال'}
                  </span>
                  <br />
                  <small style={{ opacity: 0.8 }}>{engine.detail}</small>
                </div>
              ))}
            </div>
            {(!odooReady || !erpnextReady) && (
              <div style={{
                marginTop: '1rem',
                padding: '1rem',
                background: 'var(--info-soft)',
                borderRadius: '0.375rem',
              }}>
                <strong>راهنمای تنظیمات:</strong>
                <ul style={{ marginTop: '0.5rem', paddingRight: '1.5rem' }}>
                  {!odooReady && (
                    <li>
                      برای فعال‌سازی Odoo: متغیرهای محیطی 
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ODOO_URL
                      </code>،{' '}
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ODOO_DB
                      </code>،{' '}
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ODOO_USER
                      </code> و{' '}
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ODOO_PASSWORD
                      </code> را تنظیم کنید.
                    </li>
                  )}
                  {!erpnextReady && (
                    <li>
                      برای فعال‌سازی ERPNext: متغیرهای محیطی 
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ERPNEXT_URL
                      </code>،{' '}
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ERPNEXT_API_KEY
                      </code> و{' '}
                      <code style={{ padding: '0.125rem 0.25rem', background: 'rgba(0,0,0,0.1)', borderRadius: '0.25rem' }}>
                        ERPNEXT_API_SECRET
                      </code> را تنظیم کنید.
                    </li>
                  )}
                </ul>
              </div>
            )}
          </AccountingDataPanel>
          <AccountingDataPanel title="ترازنامه" subtitle={sheet.balanced ? 'معادله برقرار است.' : 'معادله برقرار نیست.'}>
            <h3>دارایی‌ها</h3>
            <StatementTable rows={sheet.assets} totalLabel="جمع دارایی" total={sheet.asset_total} tone="debit" />
            <h3>بدهی‌ها</h3>
            <StatementTable rows={sheet.liabilities} totalLabel="جمع بدهی" total={sheet.liability_total} tone="credit" />
            <h3>سرمایه</h3>
            <StatementTable rows={sheet.equity} totalLabel="سرمایه ثبت‌شده" total={sheet.equity_total} tone="credit" />
            <p>سود و زیان بسته نشده: {money(sheet.net_income)}</p>
            <LiveTBalance
              debit={sheet.asset_total}
              credit={sheet.liabilities_and_equity}
              label="تراز آزمایشی لحظه‌ای ترازنامه"
            />
          </AccountingDataPanel>
          <AccountingDataPanel title="صورت سود و زیان">
            <h3>درآمد</h3>
            <StatementTable rows={income.revenue} totalLabel="جمع درآمد" total={income.revenue_total} tone="credit" />
            <h3>هزینه</h3>
            <StatementTable rows={income.expenses} totalLabel="جمع هزینه" total={income.expense_total} tone="debit" />
            <p>سود (زیان) خالص: <strong className={`acct-number ${(income.net_income || 0) >= 0 ? 'acct-credit' : 'acct-debit'}`}>{money(income.net_income)}</strong></p>
            <LiveTBalance
              debit={income.expense_total}
              credit={income.revenue_total}
              label="تراز آزمایشی لحظه‌ای سود و زیان"
            />
          </AccountingDataPanel>
          <AccountingDataPanel title="جریان وجوه نقد" subtitle={flow.reconciled ? 'با تغییر موجودی نقد برابر است.' : 'با تغییر موجودی نقد برابر نیست.'}>
            <h3>عملیاتی</h3>
            <FlowTable rows={flow.operating} total={flow.operating_total} />
            <h3>سرمایه‌گذاری</h3>
            <FlowTable rows={flow.investing} total={flow.investing_total} />
            <h3>تأمین مالی</h3>
            <FlowTable rows={flow.financing} total={flow.financing_total} />
          </AccountingDataPanel>
          <AccountingDataPanel title="نسبت‌ها">
            <ul>
              {books.ratios.map((row) => (
                <li key={row.key}>{row.label}: {ratioText(row.value)}</li>
              ))}
            </ul>
          </AccountingDataPanel>
          <AccountingDataPanel title="کنترل سند و پل خروجی">
            <p>
              کنترل Hordak: {books.hordak.transaction_count.toLocaleString('fa-IR')} سند،
              {' '}
              {books.hordak.balanced ? 'همه ترازند.' : 'سند نامتوازن وجود دارد.'}
            </p>
            <p>
              Beancount: {books.beancount.valid ? 'فایل دفتر معتبر است.' : 'فایل دفتر خطا دارد.'}
              {' '}
              ({books.beancount.engine})
            </p>
            <p>Odoo: {books.odoo.move_count.toLocaleString('fa-IR')} سند account.move</p>
            <p>ERPNext: {books.erpnext.entry_count.toLocaleString('fa-IR')} Journal Entry</p>
          </AccountingDataPanel>
        </>
      )}
    </div>
  )
}
