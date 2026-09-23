import { useCallback, useEffect, useState } from 'react'
import { Button, Card, EmptyState, Field } from '../ui'
import { fromLegacy } from '../../styles/tw'
import { formatNumber } from '../../utils/format'

export default function TreasuryPanel({ api, activeTab, onTabChange, canCreate, canApprove }) {
  const [rows, setRows] = useState([])
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')
  const [depositForm, setDepositForm] = useState({ deposit_date: '', amount: '', bank_account_id: '', description: '' })
  const [customerId, setCustomerId] = useState('')
  const [payAccount, setPayAccount] = useState('')

  const load = useCallback(async () => {
    try {
      if (activeTab === 'deposits') {
        const data = await api.deposits()
        setRows(data.results || [])
      } else {
        const [plan, banks] = await Promise.all([api.checkPlan(), api.checkAccounts()])
        setRows(plan.results || [])
        setAccounts(banks.results || banks.accounts || [])
      }
      setError('')
    } catch (err) {
      setError(err.message || 'خطا در بارگذاری')
    }
  }, [activeTab, api])

  useEffect(() => {
    const timer = setTimeout(() => { load() }, 0)
    return () => clearTimeout(timer)
  }, [load])

  const createDeposit = async (event) => {
    event.preventDefault()
    try {
      await api.createDeposit({
        ...depositForm,
        amount: Number(depositForm.amount) || 0,
        bank_account_id: Number(depositForm.bank_account_id),
      })
      setDepositForm({ deposit_date: '', amount: '', bank_account_id: '', description: '' })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const allocate = async (id) => {
    if (!customerId) {
      setError('شناسه مشتری را وارد کنید.')
      return
    }
    try {
      await api.allocateDeposit(id, Number(customerId))
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const pay = async (id) => {
    if (!payAccount) {
      setError('حساب بانک مبدا را انتخاب کنید.')
      return
    }
    try {
      await api.payCheck(id, Number(payAccount))
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className={fromLegacy('accounting-doc-list-toolbar')}>
        <Button type="button" variant={activeTab === 'deposits' ? 'primary' : 'ghost'} onClick={() => onTabChange('deposits')}>وجوه سرگردان</Button>
        <Button type="button" variant={activeTab === 'check-plan' ? 'primary' : 'ghost'} onClick={() => onTabChange('check-plan')}>برنامه چک</Button>
      </div>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}

      {activeTab === 'deposits' && (
        <Card title="وجوه سرگردان">
          {canCreate && (
            <form onSubmit={createDeposit} className={fromLegacy('form form-grid-2')}>
              <Field label="تاریخ"><input className={fromLegacy('ltr')} type="date" value={depositForm.deposit_date} onChange={(e) => setDepositForm({ ...depositForm, deposit_date: e.target.value })} required /></Field>
              <Field label="مبلغ"><input className={fromLegacy('ltr')} type="number" min="1" value={depositForm.amount} onChange={(e) => setDepositForm({ ...depositForm, amount: e.target.value })} required /></Field>
              <Field label="شناسه حساب بانک"><input className={fromLegacy('ltr')} value={depositForm.bank_account_id} onChange={(e) => setDepositForm({ ...depositForm, bank_account_id: e.target.value })} required /></Field>
              <Field label="شرح"><input value={depositForm.description} onChange={(e) => setDepositForm({ ...depositForm, description: e.target.value })} /></Field>
              <Button type="submit">ثبت واریز</Button>
            </form>
          )}
          {canCreate && (
            <Field label="شناسه مشتری برای تخصیص">
              <input className={fromLegacy('ltr')} value={customerId} onChange={(e) => setCustomerId(e.target.value)} />
            </Field>
          )}
          {!rows.length ? <EmptyState text="واریز نامشخصی ثبت نشده است." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>تاریخ</th><th>مبلغ</th><th>حساب</th><th>وضعیت</th><th>مشتری</th><th>سند</th><th></th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.deposit_date}</td>
                    <td>{formatNumber(row.amount)}</td>
                    <td>{row.bank_account_name}</td>
                    <td>{row.status_label}</td>
                    <td>{row.customer_name || '—'}</td>
                    <td>{row.document_code || '—'}</td>
                    <td>{row.status === 'open' && canCreate && (
                      <button type="button" className={fromLegacy('link')} onClick={() => allocate(row.id)}>تخصیص</button>
                    )}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {activeTab === 'check-plan' && (
        <Card title="برنامه پرداخت چک">
          {canApprove && (
            <Field label="حساب بانک مبدا">
              <select value={payAccount} onChange={(e) => setPayAccount(e.target.value)}>
                <option value="">انتخاب</option>
                {(Array.isArray(accounts) ? accounts : []).map((account) => (
                  <option key={account.id} value={account.id}>{account.name || account.label || account.code}</option>
                ))}
              </select>
            </Field>
          )}
          {!rows.length ? <EmptyState text="چک سررسیدی در انتظار نیست." /> : (
            <table className={fromLegacy('table')}>
              <thead><tr><th>سررسید</th><th>مبلغ</th><th>چک</th><th>مشتری</th><th>فاکتور</th><th></th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.due_date}</td>
                    <td>{formatNumber(row.amount)}</td>
                    <td>{row.check_number || '—'}</td>
                    <td>{row.customer_name}</td>
                    <td>{row.invoice_number}</td>
                    <td>{canApprove && (
                      <button type="button" className={fromLegacy('link')} onClick={() => pay(row.id)}>وصول</button>
                    )}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
