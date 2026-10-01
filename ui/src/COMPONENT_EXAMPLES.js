// ═══════════════════════════════════════════════════════════════
// ACCOUNTING MODULE - VISUAL STYLE GUIDE & COMPONENT EXAMPLES
// ═══════════════════════════════════════════════════════════════

/**
 * This file contains usage examples for the modernized accounting UI.
 * Copy these patterns into your components.
 */

// ═══ EXAMPLE 1: Professional Data Table ═══

import AccountingTable from './components/accounting/AccountingTable'
import { formatRial } from './utils/format'

function TrialBalanceExample() {
  const columns = [
    { 
      id: 'code', 
      label: 'کد', 
      type: 'code',
      minWidth: '80px',
      sortable: true 
    },
    { 
      id: 'name', 
      label: 'نام حساب',
      minWidth: '200px',
      sortable: true 
    },
    { 
      id: 'debit', 
      label: 'بدهکار', 
      type: 'numeric',
      minWidth: '140px',
      render: (value) => formatRial(value || 0),
      sortable: true 
    },
    { 
      id: 'credit', 
      label: 'بستانکار', 
      type: 'numeric',
      minWidth: '140px',
      render: (value) => formatRial(value || 0),
      sortable: true 
    },
    { 
      id: 'balance', 
      label: 'مانده', 
      type: 'numeric',
      minWidth: '140px',
      render: (value) => formatRial(Math.abs(value || 0)),
      sortable: true 
    },
  ]

  const data = [
    { id: 1, code: '101', name: 'صندوق', debit: 5000000, credit: 3000000, balance: 2000000 },
    { id: 2, code: '102', name: 'بانک', debit: 10000000, credit: 8000000, balance: 2000000 },
    // ... more rows
  ]

  const footer = (
    <tr>
      <td colSpan={2} style={{ fontWeight: '700' }}>جمع کل</td>
      <td className="col-numeric acct-number">
        <span className="acct-debit" style={{ fontWeight: '700' }}>
          {formatRial(15000000)}
        </span>
      </td>
      <td className="col-numeric acct-number">
        <span className="acct-credit" style={{ fontWeight: '700' }}>
          {formatRial(11000000)}
        </span>
      </td>
      <td colSpan={1} style={{ textAlign: 'center' }}>
        <div className="acct-balance-status acct-balance-status--balanced">
          <Icon name="check-circle" size={16} />
          <span>تراز است</span>
        </div>
      </td>
    </tr>
  )

  return (
    <AccountingTable
      columns={columns}
      data={data}
      onRowClick={(row) => console.log('Clicked:', row)}
      onSort={(columnId, direction) => console.log('Sort:', columnId, direction)}
      footer={footer}
      compact={false}
      keyField="id"
    />
  )
}

// ═══ EXAMPLE 2: Keyboard-Optimized Form ═══

function JournalEntryFormExample() {
  return (
    <form className="acct-form" onSubmit={handleSubmit}>
      <div className="acct-form-row">
        <div className="acct-form-field">
          <label className="acct-form-label acct-form-label--required">
            تاریخ سند
          </label>
          <input 
            type="text"
            className="acct-input"
            tabIndex={0}
            required
            placeholder="1403/09/15"
          />
          {error && (
            <span className="acct-form-error">
              <Icon name="alert-circle" size={12} />
              تاریخ الزامی است
            </span>
          )}
        </div>

        <div className="acct-form-field">
          <label className="acct-form-label">
            شماره سند
          </label>
          <input 
            type="number"
            className="acct-input acct-input--numeric"
            tabIndex={0}
            placeholder="12345"
          />
          <span className="acct-form-hint">
            شماره سریال سند (اختیاری)
          </span>
        </div>
      </div>

      <div className="acct-form-field">
        <label className="acct-form-label">شرح</label>
        <textarea 
          className="acct-textarea"
          rows={3}
          tabIndex={0}
          placeholder="توضیحات..."
        />
      </div>

      <button type="submit" className="acct-btn acct-btn--primary">
        <Icon name="save" size={16} />
        <span>ذخیره سند</span>
      </button>
    </form>
  )
}

// ═══ EXAMPLE 3: Financial Amount Display ═══

function AmountDisplay({ debit, credit, balance }) {
  return (
    <div style={{ display: 'flex', gap: '24px', fontSize: '14px' }}>
      {/* Debit Amount */}
      <div>
        <strong>بدهکار:</strong>{' '}
        <span className="acct-debit acct-number" style={{ fontWeight: '600' }}>
          {formatRial(debit)}
        </span>
      </div>

      {/* Credit Amount */}
      <div>
        <strong>بستانکار:</strong>{' '}
        <span className="acct-credit acct-number" style={{ fontWeight: '600' }}>
          {formatRial(credit)}
        </span>
      </div>

      {/* Balance Badge */}
      <div>
        <strong>مانده:</strong>{' '}
        {balance > 0 ? (
          <span className="acct-balance-badge acct-balance-badge--debit">
            بد {formatRial(balance)}
          </span>
        ) : balance < 0 ? (
          <span className="acct-balance-badge acct-balance-badge--credit">
            بس {formatRial(Math.abs(balance))}
          </span>
        ) : (
          <span className="acct-balance-badge acct-balance-badge--balanced">
            متعادل
          </span>
        )}
      </div>
    </div>
  )
}

// ═══ EXAMPLE 4: Liquid Glass Panel ═══

function SummaryPanel({ title, children }) {
  return (
    <div className="acct-glass-panel" style={{ padding: '20px' }}>
      <h3 style={{ 
        margin: '0 0 16px 0',
        fontSize: '16px',
        fontWeight: '700',
        color: '#111827',
        paddingBottom: '12px',
        borderBottom: '2px solid #E5E7EB'
      }}>
        {title}
      </h3>
      <div>{children}</div>
    </div>
  )
}

// ═══ EXAMPLE 5: Balance Status Component ═══

function BalanceStatus({ debit, credit }) {
  const isBalanced = Math.abs(debit - credit) < 0.01
  const difference = Math.abs(debit - credit)

  return (
    <div className={`acct-balance-status ${isBalanced ? 'acct-balance-status--balanced' : 'acct-balance-status--unbalanced'}`}>
      {isBalanced ? (
        <>
          <Icon name="check-circle" size={16} />
          <span>سند متوازن است</span>
        </>
      ) : (
        <>
          <Icon name="alert-circle" size={16} />
          <span>اختلاف: {formatRial(difference)}</span>
        </>
      )}
    </div>
  )
}

// ═══ EXAMPLE 6: Inline Editable Cell ═══

function EditableCell({ value, onChange, type = 'text', disabled = false }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={`acct-cell-input ${type === 'number' ? 'acct-input--numeric' : ''}`}
      tabIndex={disabled ? -1 : 0}
    />
  )
}

// ═══ EXAMPLE 7: Compact vs Normal Table Toggle ═══

function TableDensityToggle({ compact, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
      <span style={{ fontSize: '13px', color: '#6B7280' }}>تراکم:</span>
      <button
        type="button"
        onClick={() => onChange(true)}
        className={`acct-btn acct-btn--sm ${compact ? 'acct-btn--primary' : 'acct-btn--secondary'}`}
      >
        فشرده
      </button>
      <button
        type="button"
        onClick={() => onChange(false)}
        className={`acct-btn acct-btn--sm ${!compact ? 'acct-btn--primary' : 'acct-btn--secondary'}`}
      >
        عادی
      </button>
    </div>
  )
}

// ═══ EXAMPLE 8: Tree Node with Balance ═══

function AccountTreeNode({ code, name, balance, depth, onSelect }) {
  const balanceType = balance > 0 ? 'debit' : balance < 0 ? 'credit' : 'balanced'
  
  return (
    <div 
      style={{
        paddingRight: `${depth * 16 + 8}px`,
        padding: '8px',
        borderRadius: '6px',
        cursor: 'pointer',
        transition: 'background var(--transition-fast)'
      }}
      onClick={onSelect}
      onMouseEnter={(e) => e.currentTarget.style.background = '#F9FAFB'}
      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ 
          fontFamily: 'var(--font-mono)', 
          fontSize: '12px',
          color: '#6B7280',
          fontWeight: '600'
        }}>
          {code}
        </span>
        <span style={{ flex: 1, fontSize: '13px', fontWeight: '500' }}>
          {name}
        </span>
        {balance !== 0 && (
          <span className={`acct-number ${balanceType === 'debit' ? 'acct-debit' : 'acct-credit'}`} style={{ fontWeight: '600' }}>
            {formatRial(Math.abs(balance))}
          </span>
        )}
      </div>
    </div>
  )
}

// ═══ EXAMPLE 9: Action Button Group ═══

function DocumentActions({ onSave, onSubmit, onDelete, canSubmit }) {
  return (
    <div style={{ 
      display: 'flex', 
      gap: 'var(--acct-space-sm)', 
      justifyContent: 'flex-end',
      padding: '16px',
      background: '#F9FAFB',
      borderRadius: '8px'
    }}>
      <button
        type="button"
        onClick={onDelete}
        className="acct-btn acct-btn--danger acct-btn--sm"
      >
        <Icon name="trash-2" size={16} />
        <span>حذف</span>
      </button>
      
      <button
        type="button"
        onClick={onSave}
        className="acct-btn acct-btn--secondary"
      >
        <Icon name="save" size={16} />
        <span>ذخیره</span>
      </button>
      
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSubmit}
        className="acct-btn acct-btn--success"
      >
        <Icon name="check" size={16} />
        <span>ارسال</span>
      </button>
    </div>
  )
}

// ═══ EXAMPLE 10: Loading State ═══

function LoadingState({ message = 'در حال بارگذاری...' }) {
  return (
    <div style={{ 
      textAlign: 'center', 
      padding: '3rem 2rem',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '1rem'
    }}>
      <Icon name="loader" size={40} />
      <p style={{ color: '#6B7280', fontSize: '14px' }}>{message}</p>
    </div>
  )
}

// ═══ CSS CLASS REFERENCE ═══

/**
 * TABLE CLASSES:
 * - .acct-modern-table           → Base table styles
 * - .acct-table--compact         → Compact row height
 * - .col-numeric                 → Right-aligned numeric column
 * - .col-code                    → Monospaced code column
 * - .acct-number                 → Monospaced number display
 * 
 * FINANCIAL CLASSES:
 * - .acct-debit                  → Red debit text
 * - .acct-credit                 → Green credit text
 * - .acct-debit-cell             → Red background cell
 * - .acct-credit-cell            → Green background cell
 * - .acct-balance-badge          → Balance indicator badge
 * - .acct-balance-badge--debit   → Red debit badge
 * - .acct-balance-badge--credit  → Green credit badge
 * - .acct-balance-badge--balanced → Gray balanced badge
 * 
 * FORM CLASSES:
 * - .acct-form                   → Form container
 * - .acct-form-row               → Responsive grid row
 * - .acct-form-field             → Field container
 * - .acct-form-label             → Label text
 * - .acct-form-label--required   → Required asterisk
 * - .acct-input                  → Text input
 * - .acct-input--numeric         → Numeric input (monospaced)
 * - .acct-select                 → Select dropdown
 * - .acct-textarea               → Textarea
 * - .acct-input--error           → Error state
 * - .acct-input--success         → Success state
 * - .acct-form-error             → Error message
 * - .acct-form-hint              → Hint text
 * 
 * BUTTON CLASSES:
 * - .acct-btn                    → Base button
 * - .acct-btn--primary           → Blue primary button
 * - .acct-btn--secondary         → Gray secondary button
 * - .acct-btn--success           → Green success button
 * - .acct-btn--danger            → Red danger button
 * - .acct-btn--sm                → Small button
 * - .acct-btn--lg                → Large button
 * 
 * GLASS EFFECTS:
 * - .acct-glass-modal            → Modal with backdrop blur
 * - .acct-glass-panel            → Panel with subtle blur
 * - .acct-glass-dropdown         → Dropdown with blur
 * 
 * UTILITY CLASSES:
 * - .acct-sticky-header          → Sticky positioning
 * - .acct-scroll-container       → Horizontal scroll container
 * - .acct-sr-only                → Screen reader only
 * 
 * SPACING VARIABLES:
 * - var(--acct-space-xs)         → 4px
 * - var(--acct-space-sm)         → 8px
 * - var(--acct-space-md)         → 16px
 * - var(--acct-space-lg)         → 24px
 * - var(--acct-space-xl)         → 32px
 */
