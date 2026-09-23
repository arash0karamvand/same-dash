// ویرایشگر سطرهای سند حسابداری — Modern Keyboard-First Version

import { useState, useEffect, useRef } from 'react'
import Select from '../Select'
import MoneyInput from '../MoneyInput'
import Icon from '../icons/Icon'

/**
 * Professional Document Line Editor
 * - 100% keyboard navigable with perfect tab flow
 * - Enhanced visual focus states
 * - Real-time balance validation
 * - Monospaced numbers
 * - Inline error feedback
 */

const EMPTY_LINE = {
  detailed_id: '',
  subsidiary_id: '',
  account_id: '',
  debit: '',
  credit: '',
  description: '',
}

export default function DocumentLineEditor({
  lines = [],
  onChange,
  accountGroups = [],
  subsidiaries = [],
  details = [],
  readOnly = false,
}) {
  const [localLines, setLocalLines] = useState(lines.length > 0 ? lines : [{ ...EMPTY_LINE }])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setLocalLines(lines.length > 0 ? lines : [{ ...EMPTY_LINE }])
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [lines])

  const accountOptions = []
  for (const group of accountGroups || []) {
    for (const acc of group.accounts || []) {
      accountOptions.push({
        value: String(acc.id),
        label: `${acc.code || acc.sort_order} — ${acc.name}`,
      })
    }
  }

  const getSubsidiariesForAccount = (accountId) => {
    if (!accountId) return []
    return (subsidiaries || [])
      .filter((s) => String(s.account_id) === String(accountId))
      .map((s) => ({
        value: String(s.id),
        label: `${s.code} — ${s.name}`,
      }))
  }

  const getDetailsForSubsidiary = (subsidiaryId) => {
    if (!subsidiaryId) return []
    return (details || [])
      .filter((d) => String(d.subsidiary_id) === String(subsidiaryId))
      .map((d) => ({
        value: String(d.id),
        label: `${d.code} — ${d.name}`,
      }))
  }

  const handleLineChange = (index, field, value) => {
    const updated = [...localLines]
    updated[index] = { ...updated[index], [field]: value }

    // اگر حساب کل تغییر کرد، معین و تفصیلی را پاک کن
    if (field === 'account_id') {
      updated[index].subsidiary_id = ''
      updated[index].detailed_id = ''
    }
    // اگر معین تغییر کرد، تفصیلی را پاک کن
    if (field === 'subsidiary_id') {
      updated[index].detailed_id = ''
    }

    setLocalLines(updated)
    onChange(updated)
  }

  const addLine = () => {
    const updated = [...localLines, { ...EMPTY_LINE }]
    setLocalLines(updated)
    onChange(updated)
  }

  const removeLine = (index) => {
    if (localLines.length === 1) return // حداقل یک سطر باید باشد
    const updated = localLines.filter((_, i) => i !== index)
    setLocalLines(updated)
    onChange(updated)
  }

  // محاسبه جمع بدهکار و بستانکار
  const totals = Array.isArray(localLines) 
    ? localLines.reduce(
        (acc, line) => ({
          debit: acc.debit + (parseFloat(line.debit) || 0),
          credit: acc.credit + (parseFloat(line.credit) || 0),
        }),
        { debit: 0, credit: 0 }
      )
    : { debit: 0, credit: 0 }

  const isBalanced = Math.abs(totals.debit - totals.credit) < 0.01
  const balanceDiff = Math.abs(totals.debit - totals.credit)

  // Auto-focus first input on mount
  const firstInputRef = useRef(null)
  useEffect(() => {
    if (!readOnly && firstInputRef.current) {
      const timeout = setTimeout(() => firstInputRef.current?.focus(), 100)
      return () => clearTimeout(timeout)
    }
  }, [readOnly])

  return (
    <div className="acct-line-editor">

      <div className="acct-scroll-container">
        <table className="acct-line-editor-table">
          <thead>
            <tr>
              <th style={{ minWidth: '200px' }}>حساب کل</th>
              <th style={{ minWidth: '180px' }}>حساب معین</th>
              <th style={{ minWidth: '180px' }}>حساب تفصیلی</th>
              <th className="col-numeric" style={{ minWidth: '140px' }}>بدهکار</th>
              <th className="col-numeric" style={{ minWidth: '140px' }}>بستانکار</th>
              <th style={{ minWidth: '250px' }}>شرح</th>
              {!readOnly && <th style={{ width: '50px', textAlign: 'center' }}>عملیات</th>}
            </tr>
          </thead>
        <tbody>
          {localLines.map((line, index) => {
            const subsidiaryOpts = getSubsidiariesForAccount(line.account_id)
            const detailOpts = getDetailsForSubsidiary(line.subsidiary_id)
            const hasDebitOrCredit = line.debit || line.credit
            const isComplete = line.account_id && hasDebitOrCredit
            
            return (
              <tr key={index}>
                <td>
                  <Select
                    ref={index === 0 ? firstInputRef : null}
                    value={line.account_id || ''}
                    onChange={(e) => handleLineChange(index, 'account_id', e.target.value)}
                    options={[{ value: '', label: 'انتخاب حساب...' }, ...accountOptions]}
                    disabled={readOnly}
                    className={`acct-cell-input ${!line.account_id && index < localLines.length - 1 ? 'acct-input--error' : ''}`}
                    tabIndex={readOnly ? -1 : 0}
                    aria-label={`حساب کل سطر ${index + 1}`}
                    aria-required="true"
                  />
                </td>
                <td>
                  <Select
                    value={line.subsidiary_id || ''}
                    onChange={(e) => handleLineChange(index, 'subsidiary_id', e.target.value)}
                    options={[
                      { value: '', label: subsidiaryOpts.length > 0 ? 'انتخاب معین...' : 'بدون معین' },
                      ...subsidiaryOpts,
                    ]}
                    disabled={readOnly || !line.account_id || subsidiaryOpts.length === 0}
                    className="acct-cell-input"
                    tabIndex={readOnly || !line.account_id ? -1 : 0}
                    aria-label={`حساب معین سطر ${index + 1}`}
                  />
                </td>
                <td>
                  <Select
                    value={line.detailed_id || ''}
                    onChange={(e) => handleLineChange(index, 'detailed_id', e.target.value)}
                    options={[
                      { value: '', label: detailOpts.length > 0 ? 'انتخاب تفصیلی...' : 'بدون تفصیلی' },
                      ...detailOpts,
                    ]}
                    disabled={readOnly || !line.subsidiary_id || detailOpts.length === 0}
                    className="acct-cell-input"
                    tabIndex={readOnly || !line.subsidiary_id ? -1 : 0}
                    aria-label={`حساب تفصیلی سطر ${index + 1}`}
                  />
                </td>
                <td className={line.debit ? 'acct-debit-cell' : ''}>
                  <MoneyInput
                    value={line.debit || ''}
                    onChange={(val) => handleLineChange(index, 'debit', val)}
                    disabled={readOnly || !!line.credit}
                    className={`acct-cell-input acct-input--numeric ${line.debit ? 'acct-debit' : ''}`}
                    placeholder="0"
                    tabIndex={readOnly || !!line.credit ? -1 : 0}
                    aria-label={`بدهکار سطر ${index + 1}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Tab' && !e.shiftKey && !line.credit && line.debit) {
                        // Skip credit field if debit has value
                        e.preventDefault()
                        const nextInput = e.target.closest('tr')?.querySelector('input[type="text"]')
                        nextInput?.focus()
                      }
                    }}
                  />
                </td>
                <td className={line.credit ? 'acct-credit-cell' : ''}>
                  <MoneyInput
                    value={line.credit || ''}
                    onChange={(val) => handleLineChange(index, 'credit', val)}
                    disabled={readOnly || !!line.debit}
                    className={`acct-cell-input acct-input--numeric ${line.credit ? 'acct-credit' : ''}`}
                    placeholder="0"
                    tabIndex={readOnly || !!line.debit ? -1 : 0}
                    aria-label={`بستانکار سطر ${index + 1}`}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={line.description || ''}
                    onChange={(e) => handleLineChange(index, 'description', e.target.value)}
                    placeholder="توضیحات اختیاری..."
                    disabled={readOnly}
                    className="acct-cell-input"
                    tabIndex={readOnly ? -1 : 0}
                    aria-label={`شرح سطر ${index + 1}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey && index === localLines.length - 1) {
                        // Add new line on Enter in last row
                        e.preventDefault()
                        addLine()
                      }
                    }}
                  />
                </td>
                {!readOnly && (
                  <td style={{ textAlign: 'center' }}>
                    <button
                      type="button"
                      onClick={() => removeLine(index)}
                      disabled={localLines.length === 1}
                      className="acct-btn acct-btn--danger acct-btn--sm"
                      style={{
                        padding: '6px',
                        opacity: localLines.length === 1 ? 0.3 : 1,
                        cursor: localLines.length === 1 ? 'not-allowed' : 'pointer'
                      }}
                      tabIndex={localLines.length === 1 ? -1 : 0}
                      aria-label={`حذف سطر ${index + 1}`}
                      title={localLines.length === 1 ? 'حداقل یک سطر باید باشد' : 'حذف سطر'}
                    >
                      <Icon name="trash" size={16} />
                    </button>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
        <tfoot className="acct-line-editor-total">
          <tr>
            <td colSpan={3} style={{ fontWeight: '700' }}>جمع کل</td>
            <td className="col-numeric acct-number">
              <span className="acct-debit" style={{ fontWeight: '700' }}>
                {totals.debit.toLocaleString('fa-IR')}
              </span>
            </td>
            <td className="col-numeric acct-number">
              <span className="acct-credit" style={{ fontWeight: '700' }}>
                {totals.credit.toLocaleString('fa-IR')}
              </span>
            </td>
            <td colSpan={readOnly ? 1 : 2} style={{ textAlign: 'center' }}>
              <div className={`acct-balance-status ${isBalanced ? 'acct-balance-status--balanced' : 'acct-balance-status--unbalanced'}`}>
                {isBalanced ? (
                  <>
                    <Icon name="check" size={16} />
                    <span>سند متوازن است</span>
                  </>
                ) : (
                  <>
                    <Icon name="warning" size={16} />
                    <span>سند متوازن نیست · {balanceDiff.toLocaleString('fa-IR')}</span>
                  </>
                )}
              </div>
            </td>
          </tr>
        </tfoot>
      </table>
      </div>

      {!readOnly && (
        <div style={{ 
          marginTop: 'var(--acct-space-md)',
          display: 'flex',
          gap: 'var(--acct-space-sm)',
          alignItems: 'center'
        }}>
          <button
            type="button"
            onClick={addLine}
            className="acct-btn acct-btn--secondary"
            tabIndex={0}
          >
            <Icon name="plus" size={16} />
            <span>افزودن سطر جدید</span>
          </button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            یا از کلید <kbd className="acct-kbd">Enter</kbd> در آخرین سطر استفاده کنید
          </span>
        </div>
      )}
    </div>
  )
}
