import AccountDetailPanel from './AccountDetailPanel'
import MoneyInput from './MoneyInput'
import PersianDateInput from './PersianDateInput'
import { Button, Field } from './ui'
import { TERMS } from '../config/accountingTerms'
import { accountLevelLabel } from '../utils/accountHelpers'

const CARD_LABELS = {
  general: TERMS.generalAccount,
  subsidiary: TERMS.subsidiaryAccount,
  detailed: TERMS.detailedAccount,
  ledger: TERMS.ledger,
}

export default function LedgerSidePanelContent({
  activeCard,
  selection,
  sideTab,
  onSideTabChange,
  accountProps,
  quickDocForm,
  onQuickDocFormChange,
  onSaveQuickDoc,
  quickDocSaving,
  quickDocError,
  quickDocSuccess,
  canCreate = false,
}) {
  const cardLabel = CARD_LABELS[activeCard] || 'کارت'
  const canCreateAccount = canCreate && activeCard !== 'ledger' && selection?.level !== 'detailed'
  const showTabs = canCreate

  return (
    <>
      {showTabs && (
        <div className="ld-side__tabs" role="tablist" aria-label="نوع ساخت">
          <button
            type="button"
            role="tab"
            className={sideTab === 'account' ? 'active' : ''}
            aria-selected={sideTab === 'account'}
            onClick={() => onSideTabChange('account')}
          >
            حساب
          </button>
          <button
            type="button"
            role="tab"
            className={sideTab === 'document' ? 'active' : ''}
            aria-selected={sideTab === 'document'}
            onClick={() => onSideTabChange('document')}
          >
            {TERMS.document}
          </button>
        </div>
      )}

      <p className="ld-side__context muted small">
        کارت فعال: <strong>{cardLabel}</strong>
        {selection?.row && (
          <>
            {' · '}
            {selection.row.account_code || selection.row.full_code}
            {' — '}
            {selection.row.account_name || selection.row.name}
          </>
        )}
      </p>

      {showTabs && sideTab === 'document' ? (
        <form className="form chart-account-detail-form" onSubmit={onSaveQuickDoc}>
          {!selection ? (
            <div className="chart-account-detail-empty">
              <p className="muted">برای ثبت {TERMS.document}، ابتدا در کارت «{cardLabel}» یک حساب انتخاب کنید.</p>
            </div>
          ) : (
            <>
              {quickDocSuccess && <div className="alert-success">{quickDocSuccess}</div>}
              {quickDocError && <div className="alert-error">{quickDocError}</div>}
              <Field label={TERMS.description}>
                <input
                  value={quickDocForm.description}
                  onChange={(e) => onQuickDocFormChange({ ...quickDocForm, description: e.target.value })}
                  placeholder={`${TERMS.description} ${TERMS.document}…`}
                  required
                />
              </Field>
              <Field label="تاریخ سند">
                <PersianDateInput
                  value={quickDocForm.entry_date}
                  onChange={(v) => onQuickDocFormChange({ ...quickDocForm, entry_date: v })}
                  placeholder="اختیاری — پیش‌فرض امروز"
                  onClear={() => onQuickDocFormChange({ ...quickDocForm, entry_date: '' })}
                  clearLabel="پاک کردن"
                />
              </Field>
              <Field label={TERMS.attachCode}>
                <input
                  className="attach-code-input"
                  value={quickDocForm.attach_code}
                  onChange={(e) => onQuickDocFormChange({ ...quickDocForm, attach_code: e.target.value })}
                  placeholder="اختیاری"
                />
              </Field>
              <p className="muted small chart-account-detail-hint">
                ثبت روی{' '}
                <strong>{accountLevelLabel(selection.level)}</strong>
                {' — '}
                {selection.row.account_code}
                {' '}
                {selection.row.account_name}
              </p>
              <div className="form-grid-2">
                <Field label={TERMS.debit}>
                  <MoneyInput
                    min="0"
                    value={quickDocForm.debit}
                    onChange={(e) => onQuickDocFormChange({ ...quickDocForm, debit: e.target.value, credit: e.target.value ? '' : quickDocForm.credit })}
                    unit={TERMS.currency}
                  />
                </Field>
                <Field label={TERMS.credit}>
                  <MoneyInput
                    min="0"
                    value={quickDocForm.credit}
                    onChange={(e) => onQuickDocFormChange({ ...quickDocForm, credit: e.target.value, debit: e.target.value ? '' : quickDocForm.debit })}
                    unit={TERMS.currency}
                  />
                </Field>
              </div>
              <Button
                type="submit"
                disabled={quickDocSaving || !(Number(quickDocForm.debit) || Number(quickDocForm.credit))}
              >
                {quickDocSaving ? 'در حال ثبت…' : `ثبت ${TERMS.document}`}
              </Button>
            </>
          )}
        </form>
      ) : (
        <AccountDetailPanel
          {...accountProps}
          emptyTitle={`${cardLabel} — ساخت / ویرایش`}
          emptyText={selection
            ? 'در حال بارگذاری جزئیات حساب…'
            : `در کارت «${cardLabel}» یک حساب از لیست انتخاب کنید.`}
          emptyHint={canCreateAccount
            ? 'پس از انتخاب، می‌توانید حساب را ویرایش یا زیرمجموعه جدید ثبت کنید.'
            : activeCard === 'detailed'
              ? 'برای حساب تفصیلی فقط ویرایش امکان‌پذیر است.'
              : ''}
        />
      )}
    </>
  )
}
