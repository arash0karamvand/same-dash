# 🔄 Accounting UI Migration Guide - Before/After Examples

## Quick Reference: Old Style → New Modern Style

This guide shows how to migrate from old styles to the new modern accounting design system.

---

## 📊 Table Components

### ❌ OLD WAY (Before)
```jsx
<div className={fromLegacy('trial-balance-container')}>
  <table className="accounting-table accounting-table--compact">
    <thead>
      <tr>
        <th className="col-code">کد</th>
        <th>نام حساب</th>
        <th className="col-numeric">بدهکار</th>
      </tr>
    </thead>
    <tbody>
      {data.map((row) => (
        <tr key={row.id}>
          <td className="col-code">{row.code}</td>
          <td>{row.name}</td>
          <td className="col-numeric">{formatRial(row.debit)}</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

### ✅ NEW WAY (After)
```jsx
<div className="acct-scroll-container">
  <table className="acct-modern-table acct-table--compact">
    <thead>
      <tr>
        <th className="col-code" style={{ minWidth: '80px' }}>کد</th>
        <th style={{ minWidth: '200px' }}>نام حساب</th>
        <th className="col-numeric" style={{ minWidth: '140px' }}>بدهکار</th>
      </tr>
    </thead>
    <tbody>
      {data.map((row) => (
        <tr 
          key={row.id}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleClick(row)
          }}
        >
          <td className="col-code">{row.code}</td>
          <td style={{ fontWeight: '500' }}>{row.name}</td>
          <td className="col-numeric acct-number">
            <span className={row.debit > 0 ? 'acct-debit' : ''}>
              {formatRial(row.debit)}
            </span>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

**Key Changes:**
- `accounting-table` → `acct-modern-table`
- Add `acct-scroll-container` wrapper
- Add `acct-number` to numeric cells
- Color classes: `acct-debit` / `acct-credit`
- Add keyboard support (`tabIndex`, `onKeyDown`)
- Set `minWidth` on columns for consistency

---

## 📝 Form Inputs

### ❌ OLD WAY
```jsx
<Field label="تاریخ">
  <input
    type="text"
    value={date}
    onChange={(e) => setDate(e.target.value)}
    disabled={readOnly}
    style={{ width: '100%', padding: '0.5rem' }}
  />
</Field>
```

### ✅ NEW WAY
```jsx
<div className="acct-form-field">
  <label className="acct-form-label acct-form-label--required">
    تاریخ
  </label>
  <input
    type="text"
    value={date}
    onChange={(e) => setDate(e.target.value)}
    disabled={readOnly}
    className="acct-input"
    tabIndex={readOnly ? -1 : 0}
    required
    aria-label="تاریخ سند"
  />
  {error && (
    <span className="acct-form-error">
      <Icon name="alert-circle" size={12} />
      {error}
    </span>
  )}
</div>
```

**Key Changes:**
- `Field` → `acct-form-field`
- Add `acct-input` class
- Add `tabIndex` (skip disabled fields)
- Add ARIA labels
- Inline error messages with icons
- Required fields marked with `acct-form-label--required`

---

## 💰 Financial Amount Display

### ❌ OLD WAY
```jsx
<td className="col-numeric">
  {formatRial(row.total_debit || 0)}
</td>
<td className="col-numeric">
  {formatRial(row.total_credit || 0)}
</td>
```

### ✅ NEW WAY
```jsx
<td className="col-numeric acct-number">
  <span className={row.total_debit > 0 ? 'acct-debit' : ''}>
    {formatRial(row.total_debit || 0)}
  </span>
</td>
<td className="col-numeric acct-number">
  <span className={row.total_credit > 0 ? 'acct-credit' : ''}>
    {formatRial(row.total_credit || 0)}
  </span>
</td>
```

**Key Changes:**
- Add `acct-number` to cell
- Wrap value in `<span>` with color class
- Apply `acct-debit` or `acct-credit` conditionally

---

## 🔘 Buttons

### ❌ OLD WAY
```jsx
<Button variant="primary" onClick={handleSave}>
  ذخیره
</Button>
```

### ✅ NEW WAY
```jsx
<button
  type="button"
  onClick={handleSave}
  className="acct-btn acct-btn--primary"
  tabIndex={0}
>
  <Icon name="save" size={16} />
  <span>ذخیره</span>
</button>
```

**Key Changes:**
- `Button` → native `<button>` with `acct-btn` classes
- Always add icons for clarity
- Explicit `tabIndex={0}`
- Use semantic button types (`type="button"` or `type="submit"`)

**Button Variants:**
- `acct-btn--primary` → Blue
- `acct-btn--secondary` → Gray
- `acct-btn--success` → Green
- `acct-btn--danger` → Red

**Button Sizes:**
- `acct-btn--sm` → Small
- (default) → Normal
- `acct-btn--lg` → Large

---

## 🏷️ Balance Badges

### ❌ OLD WAY
```jsx
<td style={{ textAlign: 'center' }}>
  {row.balance > 0 ? 'بد' : row.balance < 0 ? 'بس' : '-'}
</td>
```

### ✅ NEW WAY
```jsx
<td style={{ textAlign: 'center' }}>
  {row.balance > 0.01 ? (
    <span className="acct-balance-badge acct-balance-badge--debit">
      بد
    </span>
  ) : row.balance < -0.01 ? (
    <span className="acct-balance-badge acct-balance-badge--credit">
      بس
    </span>
  ) : (
    <span style={{ color: '#9CA3AF', fontSize: '13px' }}>
      متعادل
    </span>
  )}
</td>
```

**Key Changes:**
- Use `acct-balance-badge` component
- Visual colored badges instead of text
- Threshold checking (0.01) for float precision

---

## ✨ Modal / Dialog

### ❌ OLD WAY
```jsx
<Modal title="ویرایش سند" open={showForm} onClose={closeForm}>
  <div style={{ padding: '1rem' }}>
    {/* form content */}
  </div>
</Modal>
```

### ✅ NEW WAY
```jsx
<Modal title="ویرایش سند" open={showForm} onClose={closeForm}>
  <div className="acct-glass-panel" style={{ padding: '20px' }}>
    <form className="acct-form" onSubmit={handleSubmit}>
      {/* form content with new classes */}
    </form>
  </div>
</Modal>
```

**Key Changes:**
- The Modal component now has built-in liquid glass effect
- Use `acct-form` inside modals
- Consistent padding (20px)

---

## 🌲 Tree Navigation

### ❌ OLD WAY
```jsx
<div className={fromLegacy("acct-tree-node")}>
  <button onClick={onSelect}>
    <span className={fromLegacy("acct-tree-code")}>{code}</span>
    <span className={fromLegacy("acct-tree-name")}>{name}</span>
  </button>
</div>
```

### ✅ NEW WAY
```jsx
<div 
  style={{
    paddingRight: `${depth * 16 + 8}px`,
    padding: '8px',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'background var(--transition-fast)',
    background: isActive ? '#EFF6FF' : 'transparent'
  }}
  onClick={onSelect}
  tabIndex={0}
  onMouseEnter={(e) => e.currentTarget.style.background = '#F9FAFB'}
  onMouseLeave={(e) => e.currentTarget.style.background = isActive ? '#EFF6FF' : 'transparent'}
>
  <span style={{ 
    fontFamily: 'var(--font-mono)', 
    fontSize: '12px',
    color: '#6B7280',
    fontWeight: '600'
  }}>
    {code}
  </span>
  <span style={{ fontSize: '13px', fontWeight: '500' }}>
    {name}
  </span>
</div>
```

**Key Changes:**
- Inline styles for dynamic indentation
- Active state highlighting
- Hover effects with smooth transitions
- Monospaced code display

---

## 📏 Responsive Grid Layouts

### ❌ OLD WAY
```jsx
<div style={{ 
  display: 'grid', 
  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
  gap: '1rem' 
}}>
  {/* fields */}
</div>
```

### ✅ NEW WAY
```jsx
<div className="acct-form-row">
  {/* fields automatically responsive */}
</div>
```

**Key Changes:**
- Use `acct-form-row` for automatic responsive grid
- Built-in breakpoints (200px min column width)
- Consistent gap spacing from design system

---

## 🎨 Color Coding Reference

### Debit (بدهکار)
```jsx
// Text only
<span className="acct-debit">5,000,000</span>

// Cell background
<td className="acct-debit-cell">
  <span className="acct-debit acct-number">5,000,000</span>
</td>

// Badge
<span className="acct-balance-badge acct-balance-badge--debit">
  بدهکار
</span>
```

### Credit (بستانکار)
```jsx
// Text only
<span className="acct-credit">3,000,000</span>

// Cell background
<td className="acct-credit-cell">
  <span className="acct-credit acct-number">3,000,000</span>
</td>

// Badge
<span className="acct-balance-badge acct-balance-badge--credit">
  بستانکار
</span>
```

---

## ⌨️ Keyboard Navigation Patterns

### Making a row keyboard-accessible
```jsx
// ❌ OLD
<tr onClick={handleClick}>

// ✅ NEW
<tr
  onClick={handleClick}
  tabIndex={0}
  role="button"
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleClick()
    }
  }}
>
```

### Skip disabled fields in tab flow
```jsx
// ❌ OLD
<input disabled={readOnly} />

// ✅ NEW
<input 
  disabled={readOnly}
  tabIndex={readOnly ? -1 : 0}
/>
```

---

## 📦 Layout Panels

### ❌ OLD WAY
```jsx
<Card elevated>
  <h3>عنوان</h3>
  <div>{content}</div>
</Card>
```

### ✅ NEW WAY
```jsx
<div className="acct-glass-panel" style={{ padding: '20px' }}>
  <h3 style={{ 
    margin: '0 0 16px 0',
    fontSize: '16px',
    fontWeight: '700',
    color: '#111827',
    paddingBottom: '12px',
    borderBottom: '2px solid #E5E7EB'
  }}>
    عنوان
  </h3>
  <div>{content}</div>
</div>
```

**Key Changes:**
- `Card` → `acct-glass-panel`
- Consistent padding (20px)
- Structured heading with bottom border
- Premium glass effect

---

## 📊 Loading States

### ❌ OLD WAY
```jsx
{loading && <div className={fromLegacy("loading")}>در حال بارگذاری…</div>}
```

### ✅ NEW WAY
```jsx
{loading && (
  <div style={{ 
    textAlign: 'center', 
    padding: '3rem 2rem',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '1rem'
  }}>
    <Icon name="loader" size={40} />
    <p style={{ color: '#6B7280', fontSize: '14px' }}>
      در حال بارگذاری داده‌های مالی...
    </p>
  </div>
)}
```

**Key Changes:**
- Centered layout with flexbox
- Larger icon (40px)
- Descriptive message
- Consistent spacing

---

## 🔤 Typography

### Numbers (Monospaced)
```jsx
// ❌ OLD
<span>{formatRial(amount)}</span>

// ✅ NEW
<span className="acct-number">
  {formatRial(amount)}
</span>
```

### Code Display
```jsx
// ❌ OLD
<td className="col-code">{code}</td>

// ✅ NEW
<td className="col-code">
  {code}
</td>
```
*(Already correct, `col-code` applies monospaced font)*

---

## 🚀 Quick Migration Checklist

When updating a component:

1. **Tables**
   - [ ] Replace `accounting-table` → `acct-modern-table`
   - [ ] Add `acct-number` to numeric cells
   - [ ] Apply `acct-debit` / `acct-credit` colors
   - [ ] Add keyboard navigation (`tabIndex`, `onKeyDown`)
   - [ ] Set `minWidth` on columns

2. **Forms**
   - [ ] Replace `Field` → `acct-form-field`
   - [ ] Use `acct-input`, `acct-select`, `acct-textarea`
   - [ ] Add `tabIndex` management
   - [ ] Add ARIA labels
   - [ ] Add inline error messages

3. **Buttons**
   - [ ] Use `acct-btn` classes
   - [ ] Add icons
   - [ ] Set proper `type` attribute

4. **Financial Data**
   - [ ] Wrap amounts in color classes
   - [ ] Use badge components for balance
   - [ ] Apply monospaced fonts

5. **Panels/Cards**
   - [ ] Use `acct-glass-panel` for containers
   - [ ] Consistent padding (20px)
   - [ ] Structured headings

6. **Accessibility**
   - [ ] All interactive elements have `tabIndex`
   - [ ] Disabled fields have `tabIndex={-1}`
   - [ ] Buttons have `role="button"` if not `<button>`
   - [ ] Add ARIA labels where needed

---

## 💡 Pro Tips

### Use CSS Variables for Spacing
```jsx
// ❌ Don't use arbitrary values
style={{ marginTop: '15px' }}

// ✅ Use design system tokens
style={{ marginTop: 'var(--acct-space-md)' }}
```

### Consistent Number Formatting
```jsx
// Always use formatRial for amounts
<span className="acct-number">
  {formatRial(value)}
</span>
```

### Balance Threshold
```jsx
// Use 0.01 threshold for float comparisons
const isDebit = balance > 0.01
const isCredit = balance < -0.01
const isBalanced = Math.abs(balance) < 0.01
```

### Keyboard + Mouse Support
```jsx
// Support both interaction methods
<div
  onClick={handleClick}
  tabIndex={0}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleClick()
    }
  }}
>
```

---

## 📚 Additional Resources

- **Full Design System**: `ui/src/styles/accounting-modern.css`
- **Component Examples**: `ui/src/COMPONENT_EXAMPLES.js`
- **Complete Guide**: `UI_UX_REFACTORING_COMPLETE.md`
- **Refactored Components**: Check these files for real-world examples:
  - `TrialBalanceView.jsx`
  - `DocumentLineEditor.jsx`
  - `LedgerExplorer.jsx`
  - `DocumentForm.jsx`
  - `AccountingTable.jsx`

---

## 🎯 Migration Priority

1. **High Priority** (Accountant-facing, used daily)
   - Trial balance reports
   - Journal entry forms
   - Ledger views
   - Document management

2. **Medium Priority** (Administrative, used weekly)
   - Account management
   - Report filters
   - Treasury panels

3. **Low Priority** (Configuration, used occasionally)
   - Settings forms
   - Admin panels

---

**Remember:** The goal is consistency. Follow the patterns, use the design system classes, and maintain keyboard accessibility throughout.
