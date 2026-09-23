// صفحه خزانه (وجوه سرگردان و برنامه چک)

import { useEffect, useCallback, useMemo, useState } from 'react'
import { accountingApi, customersApi } from '../api/client'
import { resultList } from '../api/accounting'
import DepositsManager from '../components/accounting/DepositsManager'
import CheckPlan from '../components/accounting/CheckPlan'
import { AccountingPageHeader, AccountingSummary } from '../components/accounting/AccountingERP'
import { formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

export default function AccountingTreasury({ tab = 'deposits' }) {
  const [deposits, setDeposits] = useState([])
  const [checks, setChecks] = useState([])
  const [customers, setCustomers] = useState([])
  const [depositAccounts, setDepositAccounts] = useState([])
  const [loading, setLoading] = useState(false)

  const loadDeposits = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.deposits()
      setDeposits(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری وجوه سرگردان:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadChecks = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.checkPlan()
      setChecks(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری برنامه چک:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadCustomers = useCallback(async () => {
    try {
      const result = await customersApi.list({ limit: 1000 })
      setCustomers(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری مشتریان:', err)
    }
  }, [])

  const loadDepositAccounts = useCallback(async () => {
    try {
      setDepositAccounts(resultList(await accountingApi.checkAccounts()))
    } catch (err) {
      console.error('خطا در بارگذاری حساب‌های بانکی:', err)
    }
  }, [])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadCustomers()
      loadDepositAccounts()
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [loadCustomers, loadDepositAccounts])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (tab === 'deposits') loadDeposits()
      else if (tab === 'check-plan') loadChecks()
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [tab, loadDeposits, loadChecks])

  const handleAllocateDeposit = async (depositId, customerId) => {
    await accountingApi.allocateDeposit(depositId, customerId)
  }

  const handlePayCheck = async (checkId, depositAccountId) => {
    await accountingApi.payCheck(checkId, depositAccountId)
  }

  const summary = useMemo(() => ({
    deposits: deposits.reduce((sum, item) => sum + Number(item.amount || 0), 0),
    pendingChecks: checks
      .filter((item) => item.status !== 'paid')
      .reduce((sum, item) => sum + Number(item.amount || 0), 0),
  }), [deposits, checks])

  return (
    <div className={fromLegacy('accounting-treasury-page')}>
      <AccountingPageHeader
        eyebrow="عملیات نقد و بانک"
        title={tab === 'check-plan' ? 'برنامه چک‌ها' : 'وجوه واریزی'}
        description={tab === 'check-plan'
          ? 'کنترل سررسید و ثبت پرداخت چک‌های صادرشده'
          : 'شناسایی و تخصیص وجوه واریزی به مشتریان'}
      />

      <AccountingSummary items={[
        { label: 'کل وجوه واریزی', value: formatRial(summary.deposits) },
        { label: 'تعهد چک‌های باز', value: formatRial(summary.pendingChecks) },
        { label: 'تعداد چک باز', value: checks.filter((item) => item.status !== 'paid').length.toLocaleString('fa-IR') },
      ]} />

      {tab === 'deposits' && (
        <DepositsManager
          deposits={deposits}
          customers={customers}
          onAllocate={handleAllocateDeposit}
          onRefresh={loadDeposits}
          loading={loading}
        />
      )}

      {tab === 'check-plan' && (
        <CheckPlan
          checks={checks}
          depositAccounts={depositAccounts}
          onPay={handlePayCheck}
          onRefresh={loadChecks}
          loading={loading}
        />
      )}

    </div>
  )
}
