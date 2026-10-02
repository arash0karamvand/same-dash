// صفحه مدیریت حساب‌ها (Chart of Accounts)

import { useState, useEffect, useCallback, useMemo } from 'react'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import { useConfirm } from '../context/ConfirmContext'
import AccountTreeView from '../components/accounting/AccountTreeView'
import AccountFormModal from '../components/accounting/AccountFormModal'
import AccountMappingsPanel from '../components/accounting/AccountMappingsPanel'
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
  const confirm = useConfirm()

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
            .filter((sub) => Number(sub.account_id) === Number(account.id))
            .map((sub) => ({
              ...sub,
              details: details.filter((detail) => Number(detail.subsidiary_id) === Number(sub.id)),
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

  const postableAccounts = useMemo(() => {
    const rows = []
    accountGroups.forEach((group) => {
      ;(group.accounts || []).forEach((account) => {
        const subsidiaries = account.subsidiaries || []
        if (!subsidiaries.length) {
          rows.push({
            level: 'general',
            id: account.id,
            code: account.full_code || account.code,
            name: account.name,
          })
        }
        subsidiaries.forEach((sub) => {
          const details = sub.details || []
          if (!details.length) {
            rows.push({
              level: 'subsidiary',
              id: sub.id,
              code: sub.full_code || sub.code,
              name: sub.name,
            })
          }
          details.forEach((detail) => {
            rows.push({
              level: 'detailed',
              id: detail.id,
              code: detail.full_code || detail.code,
              name: detail.name,
            })
          })
        })
      })
    })
    return rows
  }, [accountGroups])

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

  const handleCreateChild = (account, level) => {
    if (level === 'general') {
      setFormConfig({
        level: 'subsidiary',
        account: null,
        parentAccount: account,
        parentSubsidiary: null,
      })
      setShowForm(true)
      return
    }
    if (level !== 'subsidiary') return
    let parentAccount = null
    for (const group of accountGroups) {
      parentAccount = group.accounts.find((item) => item.id === account.account_id)
      if (parentAccount) break
    }
    if (!parentAccount) {
      alert('حساب کل این معین پیدا نشد.')
      return
    }
    setFormConfig({
      level: 'detailed',
      account: null,
      parentAccount,
      parentSubsidiary: account,
    })
    setShowForm(true)
  }

  const handleDelete = async (account, level) => {
    const ok = await confirm({
      title: 'حذف حساب',
      message: `حساب «${account.name}» حذف شود؟ اگر زیرحساب داشته باشد حذف نمی‌شود. اگر رکورد داشته باشد هم حذف نمی‌شود و باید غیرفعال شود.`,
      confirmText: 'حذف',
      variant: 'danger',
    })
    if (!ok) return
    try {
      if (level === 'general') await api.deleteGeneralAccount(account.id)
      else if (level === 'subsidiary') await api.deleteSubsidiary(account.id)
      else await api.deleteDetailed(account.id)
      if (selectedAccount?.account?.id === account.id && selectedAccount.level === level) {
        setSelectedAccount(null)
      }
      loadAccounts()
    } catch (err) {
      alert(err.message || 'حذف حساب ممکن نشد.')
    }
  }

  const handleSave = async (formData, level) => {
    if (level === 'general') {
      if (formConfig.account) {
        await api.updateGeneralAccount(formConfig.account.id, formData)
      } else {
        await api.createGeneral(formData)
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
    <div className={fromLegacy('accounting-chart-page min-w-0 max-w-full')}>
      <AccountingPageHeader
        eyebrow="ساختار کدینگ"
        title="درخت حساب‌ها"
        description="روی ردیف بزنید تا زیرحساب‌ها باز شوند. رکوردها با دکمهٔ «رکوردها» باز می‌شوند. از همان‌جا حساب و رکورد را بسازید، ویرایش یا حذف کنید."
        actions={(
          <Button variant="primary" onClick={handleCreateGeneral}>
            <Icon name="plus" size={16} />
            <span>حساب کل جدید</span>
          </Button>
        )}
      />

      <AccountingToolbar>
        <label className="acct-chart-search">
          <Icon name="search" size={16} />
          <input
            className={fromLegacy("search-input")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="جست‌وجوی کد یا عنوان حساب…"
          />
        </label>
        <span className="acct-chart-count">
          {filteredGroups.reduce((count, group) => count + group.accounts.length, 0).toLocaleString('fa-IR')} حساب کل
        </span>
      </AccountingToolbar>

      {loading ? (
        <div className={fromLegacy("loading")}>در حال بارگذاری کدینگ حساب‌ها…</div>
      ) : (
        <AccountingDataPanel title="ساختار حساب‌ها" subtitle="زیرحساب با کلیک روی ردیف باز می‌شود. رکوردها فقط با دکمهٔ «رکوردها».">
          <AccountTreeView
            accountGroups={filteredGroups}
            postableAccounts={postableAccounts}
            onEdit={handleEdit}
            onCreateChild={handleCreateChild}
            onDelete={handleDelete}
            onSelect={setSelectedAccount}
            selectedKey={selectedAccount ? `${selectedAccount.level}:${selectedAccount.account.id}` : ''}
            expandAll={Boolean(search.trim())}
          />
        </AccountingDataPanel>
      )}

      <AccountMappingsPanel api={api} accounts={postableAccounts} />

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
