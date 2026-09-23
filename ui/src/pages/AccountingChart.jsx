// صفحه مدیریت حساب‌ها (Chart of Accounts)

import { useState, useEffect, useCallback, useMemo } from 'react'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import AccountTreeView from '../components/accounting/AccountTreeView'
import AccountFormModal from '../components/accounting/AccountFormModal'
import { AccountingDataPanel, AccountingPageHeader, AccountingToolbar } from '../components/accounting/AccountingERP'
import { Button } from '../components/ui'
import Icon from '../components/icons/Icon'
import { fromLegacy } from '../styles/tw'

export default function AccountingChart() {
  const [accountGroups, setAccountGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedAccount, setSelectedAccount] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [formConfig, setFormConfig] = useState({
    level: 'general',
    account: null,
    parentAccount: null,
    parentSubsidiary: null,
  })

  const api = accountingApi

  const loadAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const [accountPayload, subsidiaryPayload, detailPayload] = await Promise.all([
        api.accounts(),
        api.subsidiaries(),
        api.details(),
      ])
      const accounts = resultList(accountPayload)
      const subsidiaries = resultList(subsidiaryPayload)
      const details = resultList(detailPayload)
      const enriched = accounts.map((group) => ({
        ...group,
        accounts: (group.accounts || []).map((account) => ({
          ...account,
          subsidiaries: subsidiaries
            .filter((sub) => sub.account_id === account.id)
            .map((sub) => ({
              ...sub,
              details: details.filter((detail) => detail.subsidiary_id === sub.id),
            })),
        })),
      }))
      setAccountGroups(enriched)
    } catch (err) {
      console.error('خطا در بارگذاری حساب‌ها:', err)
      alert('خطا در بارگذاری حساب‌ها: ' + err.message)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    const timeoutId = setTimeout(loadAccounts, 0)
    return () => clearTimeout(timeoutId)
  }, [loadAccounts])

  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return accountGroups
    return accountGroups.map((group) => ({
      ...group,
      accounts: (group.accounts || []).filter((account) => {
        const accountText = `${account.code} ${account.name}`.toLowerCase()
        return accountText.includes(query)
          || (account.subsidiaries || []).some((sub) =>
            `${sub.code} ${sub.name}`.toLowerCase().includes(query)
            || (sub.details || []).some((detail) =>
              `${detail.code} ${detail.name}`.toLowerCase().includes(query)))
      }),
    })).filter((group) => group.accounts.length)
  }, [accountGroups, search])

  const handleCreateGeneral = () => {
    setFormConfig({
      level: 'general',
      account: null,
      parentAccount: null,
      parentSubsidiary: null,
    })
    setShowForm(true)
  }

  const handleEdit = (account, level) => {
    let parentAccount = null
    let parentSubsidiary = null

    if (level === 'subsidiary') {
      // پیدا کردن حساب کل والد
      for (const group of accountGroups) {
        parentAccount = group.accounts.find((a) => a.id === account.account_id)
        if (parentAccount) break
      }
    } else if (level === 'detailed') {
      // پیدا کردن معین والد و حساب کل
      for (const group of accountGroups) {
        for (const acc of group.accounts) {
          parentSubsidiary = acc.subsidiaries?.find((s) => s.id === account.subsidiary_id)
          if (parentSubsidiary) {
            parentAccount = acc
            break
          }
        }
        if (parentSubsidiary) break
      }
    }

    setFormConfig({
      level,
      account,
      parentAccount,
      parentSubsidiary,
    })
    setShowForm(true)
  }

  const handleSave = async (formData, level) => {
    if (level === 'general') {
      if (formConfig.account) {
        await api.updateGeneralAccount(formConfig.account.id, formData)
      } else {
        await api.create(formData)
      }
    } else if (level === 'subsidiary') {
      if (formConfig.account) {
        await api.updateSubsidiary(formConfig.account.id, formData)
      } else {
        await api.createSubsidiary({
          ...formData,
          account_id: formConfig.parentAccount.id,
        })
      }
    } else if (level === 'detailed') {
      if (formConfig.account) {
        await api.updateDetailed(formConfig.account.id, formData)
      } else {
        await api.createDetailed({
          ...formData,
          subsidiary_id: formConfig.parentSubsidiary.id,
          account_id: formConfig.parentAccount.id,
        })
      }
    }
    
    setShowForm(false)
    loadAccounts()
  }

  return (
    <div className={fromLegacy('accounting-chart-page')}>
      <AccountingPageHeader
        eyebrow="ساختار کدینگ"
        title="درخت حساب‌ها"
        description="نقشه سلسله‌مراتبی حساب‌های کل، معین و تفصیلی"
        actions={(
          <Button variant="primary" onClick={handleCreateGeneral}>
            <Icon name="plus" size={16} />
            <span>حساب کل جدید</span>
          </Button>
        )}
      />

      <AccountingToolbar>
        <Icon name="search" size={16} />
        <input
          className={fromLegacy("search-input")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="جست‌وجوی کد یا عنوان حساب…"
        />
        <span className={fromLegacy("muted small")}>
          {filteredGroups.reduce((count, group) => count + group.accounts.length, 0).toLocaleString('fa-IR')} حساب کل
        </span>
      </AccountingToolbar>

      {loading ? (
        <div className={fromLegacy("loading")}>در حال بارگذاری کدینگ حساب‌ها…</div>
      ) : (
        <div className={fromLegacy("acct-chart-workspace")}>
          <AccountingDataPanel title="ساختار حساب‌ها">
            <AccountTreeView
              accountGroups={filteredGroups}
              onEdit={handleEdit}
              onSelect={setSelectedAccount}
              selectedId={selectedAccount?.account?.id}
            />
          </AccountingDataPanel>
          <AccountingDataPanel title="مشخصات حساب" className="acct-chart-inspector">
            {selectedAccount ? (
              <dl className={fromLegacy("acct-account-inspector acct-inspector")}>
                <div><dt>سطح</dt><dd>{selectedAccount.level === 'general' ? 'کل' : selectedAccount.level === 'subsidiary' ? 'معین' : 'تفصیلی'}</dd></div>
                <div><dt>کد</dt><dd className="acct-number">{selectedAccount.account.full_code || selectedAccount.account.code || '—'}</dd></div>
                <div><dt>عنوان</dt><dd>{selectedAccount.account.name}</dd></div>
                <div><dt>وضعیت</dt><dd>{selectedAccount.account.is_active === false ? 'غیرفعال' : 'فعال'}</dd></div>
              </dl>
            ) : (
              <p className={fromLegacy("muted acct-empty-inspector")}>یک حساب را از درخت انتخاب کنید.</p>
            )}
          </AccountingDataPanel>
        </div>
      )}

      <AccountFormModal
        open={showForm}
        onClose={() => setShowForm(false)}
        level={formConfig.level}
        account={formConfig.account}
        parentAccount={formConfig.parentAccount}
        parentSubsidiary={formConfig.parentSubsidiary}
        onSave={handleSave}
      />
    </div>
  )
}
