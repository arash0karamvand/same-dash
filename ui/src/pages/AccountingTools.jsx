// ابزار ورود گروهی اسناد دفتر قانونی شرکت

import { accountingApi } from '../api/client'
import ExcelUploader from '../components/accounting/ExcelUploader'
import { AccountingPageHeader } from '../components/accounting/AccountingERP'
import { fromLegacy } from '../styles/tw'

export default function AccountingTools() {
  return (
    <div className={fromLegacy('accounting-tools-page')}>
      <AccountingPageHeader
        eyebrow="عملیات گروهی"
        title="ورود اطلاعات از اکسل"
        description="اعتبارسنجی و ثبت گروهی اسناد حسابداری از فایل اکسل"
      />

      <ExcelUploader api={accountingApi} />
    </div>
  )
}
