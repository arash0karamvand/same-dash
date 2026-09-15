import { Button, Field } from './ui'
import { TERMS } from '../config/accountingTerms'
import { accountLevelLabel } from '../utils/accountHelpers'
import { fromLegacy } from '../styles/tw.js'

export default function AccountDetailPanel({
  selected,
  editForm,
  onEditFormChange,
  childForm,
  onChildFormChange,
  panelTab,
  onPanelTabChange,
  onSaveEdit,
  onSaveChild,
  editSaving = false,
  childSaving = false,
  canCreate = false,
  canEdit = false,
  onClose,
  showClose = false,
  emptyTitle = 'جزئیات حساب',
  emptyText = 'یک حساب از فهرست انتخاب کنید.',
  emptyHint = '',
}) {
  if (!selected || !editForm) {
    return (
      <div className={fromLegacy("chart-account-detail-empty")}>
        <h3 className={fromLegacy("chart-account-detail-title")}>{emptyTitle}</h3>
        <p className={fromLegacy("muted")}>{emptyText}</p>
        {emptyHint && <p className={fromLegacy("muted small")}>{emptyHint}</p>}
      </div>
    )
  }

  return (
    <>
      <div className={fromLegacy("chart-account-detail-head")}>
        <h3 className={fromLegacy("chart-account-detail-title")}>{accountLevelLabel(selected.level)}</h3>
        {showClose && onClose && (
          <button type="button" className={fromLegacy("chart-account-detail-close link")} onClick={onClose} aria-label="بستن">
            ×
          </button>
        )}
      </div>

      <p className={fromLegacy("chart-account-detail-path muted small")}>
        {editForm.full_code ? editForm.full_code : editForm.code}
        {' — '}
        {editForm.name}
      </p>

      {canCreate && selected.level !== 'detailed' && (
        <div className={fromLegacy("chart-account-detail-tabs")} role="tablist">
          <button
            type="button"
            role="tab"
            className={panelTab === 'edit' ? 'active' : ''}
            aria-selected={panelTab === 'edit'}
            onClick={() => onPanelTabChange('edit')}
          >
            ویرایش
          </button>
          <button
            type="button"
            role="tab"
            className={panelTab === 'add' ? 'active' : ''}
            aria-selected={panelTab === 'add'}
            onClick={() => onPanelTabChange('add')}
          >
            {selected.level === 'general'
              ? `+ ${TERMS.subsidiaryAccount}`
              : `+ ${TERMS.detailedAccount}`}
          </button>
        </div>
      )}

      {panelTab === 'edit' || selected.level === 'detailed' ? (
        <form onSubmit={onSaveEdit} className={fromLegacy("form chart-account-detail-form")}>
          {selected.level === 'general' ? (
            <Field label={TERMS.accountCode}>
              <input value={editForm.code} readOnly disabled />
            </Field>
          ) : (
            <Field label={TERMS.accountCode}>
              <input
                value={editForm.code}
                onChange={(e) => onEditFormChange({ ...editForm, code: e.target.value })}
                required
                disabled={!canEdit}
              />
            </Field>
          )}
          <Field label={TERMS.accountTitle}>
            <input
              value={editForm.name}
              onChange={(e) => onEditFormChange({ ...editForm, name: e.target.value })}
              required
              disabled={!canEdit}
            />
          </Field>
          {editForm.class_label && (
            <p className={fromLegacy("muted small chart-account-detail-hint")}>طبقه: {editForm.class_label}</p>
          )}
          {editForm.general_name && selected.level !== 'general' && (
            <p className={fromLegacy("muted small chart-account-detail-hint")}>{TERMS.generalAccount}: {editForm.general_name}</p>
          )}
          {editForm.subsidiary_name && (
            <p className={fromLegacy("muted small chart-account-detail-hint")}>{TERMS.subsidiaryAccount}: {editForm.subsidiary_name}</p>
          )}
          <label className={fromLegacy("checkbox-field")}>
            <input
              type="checkbox"
              checked={editForm.is_active}
              onChange={(e) => onEditFormChange({ ...editForm, is_active: e.target.checked })}
              disabled={!canEdit}
            />
            فعال (غیرفعال = حذف نرم)
          </label>
          {canEdit ? (
            <Button type="submit" disabled={editSaving}>
              {editSaving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
            </Button>
          ) : (
            <p className={fromLegacy("muted small")}>برای ویرایش، مجوز «ویرایش حسابداری» لازم است.</p>
          )}
        </form>
      ) : (
        <form onSubmit={onSaveChild} className={fromLegacy("form chart-account-detail-form")}>
          <p className={fromLegacy("muted small chart-account-detail-hint")}>
            زیرمجموعه برای{' '}
            <strong>
              {editForm.full_code || editForm.code} — {editForm.name}
            </strong>
          </p>
          <div className={fromLegacy("form-grid-2")}>
            <Field label={TERMS.accountCode}>
              <input
                value={childForm.code}
                onChange={(e) => onChildFormChange({ ...childForm, code: e.target.value })}
                required
                autoFocus
              />
            </Field>
            <Field label={TERMS.accountTitle}>
              <input
                value={childForm.name}
                onChange={(e) => onChildFormChange({ ...childForm, name: e.target.value })}
                required
              />
            </Field>
          </div>
          <Button type="submit" disabled={childSaving}>
            {childSaving
              ? 'در حال ثبت…'
              : selected.level === 'general'
                ? `ثبت ${TERMS.subsidiaryAccount}`
                : `ثبت ${TERMS.detailedAccount}`}
          </Button>
        </form>
      )}
    </>
  )
}
