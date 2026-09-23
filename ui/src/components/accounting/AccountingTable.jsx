// Modern Accounting Table Component — Reusable Professional Data Grid

import { forwardRef } from 'react'
import Icon from '../icons/Icon'

/**
 * Professional Accounting Table Component
 * 
 * Features:
 * - Zebra striping for enhanced readability
 * - Sticky headers for long scrolls
 * - Monospaced fonts for financial data
 * - Keyboard accessible
 * - Sortable columns (optional)
 * - Compact and normal density modes
 * - Color-coded financial data
 * 
 * @example
 * <AccountingTable
 *   columns={[
 *     { id: 'code', label: 'کد', type: 'code' },
 *     { id: 'name', label: 'نام حساب' },
 *     { id: 'debit', label: 'بدهکار', type: 'numeric' },
 *     { id: 'credit', label: 'بستانکار', type: 'numeric' },
 *   ]}
 *   data={rows}
 *   onRowClick={handleRowClick}
 *   compact={false}
 * />
 */

const AccountingTable = forwardRef(({
  columns = [],
  data = [],
  onRowClick,
  onSort,
  sortBy,
  sortDirection = 'asc',
  compact = false,
  loading = false,
  emptyMessage = 'داده‌ای برای نمایش وجود ندارد',
  footer,
  className = '',
  keyField = 'id',
}, ref) => {

  const handleRowClick = (row, index) => {
    if (onRowClick && typeof onRowClick === 'function') {
      onRowClick(row, index)
    }
  }

  const handleSort = (columnId) => {
    if (onSort && typeof onSort === 'function') {
      const newDirection = sortBy === columnId && sortDirection === 'asc' ? 'desc' : 'asc'
      onSort(columnId, newDirection)
    }
  }

  const getColumnClass = (column) => {
    const classes = []
    
    if (column.type === 'numeric' || column.numeric) {
      classes.push('col-numeric', 'acct-number')
    }
    
    if (column.type === 'code') {
      classes.push('col-code')
    }
    
    if (column.className) {
      classes.push(column.className)
    }
    
    return classes.join(' ')
  }

  const getCellValue = (row, column) => {
    const value = column.accessor 
      ? column.accessor(row) 
      : row[column.id]
    
    // If column has a custom render function
    if (column.render && typeof column.render === 'function') {
      return column.render(value, row)
    }
    
    return value
  }

  const getCellClass = (row, column) => {
    const classes = [getColumnClass(column)]
    
    // Add financial coloring for debit/credit
    if (column.id === 'debit' || column.type === 'debit') {
      const value = parseFloat(row[column.id]) || 0
      if (value > 0) classes.push('acct-debit')
    }
    
    if (column.id === 'credit' || column.type === 'credit') {
      const value = parseFloat(row[column.id]) || 0
      if (value > 0) classes.push('acct-credit')
    }
    
    if (column.id === 'balance') {
      const value = parseFloat(row[column.id]) || 0
      if (value > 0.01) classes.push('acct-debit')
      else if (value < -0.01) classes.push('acct-credit')
    }
    
    return classes.join(' ')
  }

  if (loading) {
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
        <p style={{ color: '#6B7280', fontSize: '14px' }}>در حال بارگذاری...</p>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div style={{ 
        textAlign: 'center', 
        padding: '3rem 2rem',
        color: '#9CA3AF'
      }}>
        <Icon name="inbox" size={48} style={{ opacity: 0.5, marginBottom: '1rem' }} />
        <p style={{ fontSize: '14px' }}>{emptyMessage}</p>
      </div>
    )
  }

  const isClickable = typeof onRowClick === 'function'

  return (
    <div className="acct-scroll-container">
      <table 
        ref={ref}
        className={`acct-modern-table ${compact ? 'acct-table--compact' : ''} ${className}`}
      >
        <thead>
          <tr>
            {columns.map((column) => {
              const isSortable = column.sortable && onSort
              const isSorted = sortBy === column.id
              
              return (
                <th 
                  key={column.id}
                  className={`${getColumnClass(column)} ${isSortable ? 'sortable' : ''}`}
                  style={{ 
                    minWidth: column.minWidth,
                    width: column.width,
                    textAlign: column.align || (column.type === 'numeric' ? 'left' : 'right')
                  }}
                  onClick={() => isSortable && handleSort(column.id)}
                  tabIndex={isSortable ? 0 : undefined}
                  role={isSortable ? 'button' : undefined}
                  aria-sort={isSorted ? (sortDirection === 'asc' ? 'ascending' : 'descending') : undefined}
                  onKeyDown={(e) => {
                    if (isSortable && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault()
                      handleSort(column.id)
                    }
                  }}
                >
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '6px',
                    justifyContent: column.type === 'numeric' ? 'flex-start' : 'flex-end'
                  }}>
                    {column.label}
                    {isSortable && (
                      <Icon 
                        name={isSorted && sortDirection === 'desc' ? 'arrow-down' : 'arrow-up'} 
                        size={12}
                        style={{ 
                          opacity: isSorted ? 1 : 0.3,
                          transition: 'opacity var(--transition-fast)'
                        }}
                      />
                    )}
                  </div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={row[keyField] || index}
              onClick={() => handleRowClick(row, index)}
              style={{ cursor: isClickable ? 'pointer' : 'default' }}
              tabIndex={isClickable ? 0 : undefined}
              role={isClickable ? 'button' : undefined}
              onKeyDown={(e) => {
                if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  handleRowClick(row, index)
                }
              }}
            >
              {columns.map((column) => (
                <td 
                  key={column.id}
                  className={getCellClass(row, column)}
                  style={{
                    textAlign: column.align || (column.type === 'numeric' ? 'left' : 'right'),
                    ...(column.cellStyle || {})
                  }}
                >
                  {getCellValue(row, column)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer && (
          <tfoot>
            {footer}
          </tfoot>
        )}
      </table>
    </div>
  )
})

AccountingTable.displayName = 'AccountingTable'

export default AccountingTable
