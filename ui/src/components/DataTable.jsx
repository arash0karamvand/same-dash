// کامپوننت جامع DataTable با قابلیت‌های پیشرفته
// شامل: sort, filter, pagination, inline edit, bulk actions, column visibility

import { useMemo, useState } from 'react'
import Icon from './icons/Icon'
import { Badge, Button } from './ui'
import { cn, tw } from '../styles/tw'
import { toPersianDigits } from '../utils/jalali'

function SortIcon({ direction }) {
  if (!direction) {
    return <Icon name="chevron-up-down" size={14} className="text-muted opacity-50" />
  }
  return (
    <Icon
      name={direction === 'asc' ? 'chevron-up' : 'chevron-down'}
      size={14}
      className="text-accent"
    />
  )
}

function ColumnVisibilityMenu({ columns, visibility, onChange }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2"
      >
        <Icon name="columns" size={16} />
        ستون‌ها
      </Button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full right-0 z-20 mt-1 w-56 rounded-pill border border-jelly-rim bg-layer-3 p-2 shadow-jelly-raised">
            <div className="space-y-1">
              {columns.map((col) => (
                <label
                  key={col.key}
                  className="flex cursor-pointer items-center gap-2 rounded-capsule px-3 py-2 text-sm hover:bg-layer-1"
                >
                  <input
                    type="checkbox"
                    checked={visibility[col.key] !== false}
                    onChange={(e) =>
                      onChange({ ...visibility, [col.key]: e.target.checked })
                    }
                    className="h-4 w-4 accent-accent"
                  />
                  <span>{col.label}</span>
                </label>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function BulkActionsToolbar({ selectedCount, actions, onAction, onClear }) {
  return (
    <div className="flex items-center gap-3 rounded-capsule border border-jelly-rim bg-layer-2 px-4 py-2 shadow-[inset_0_1px_0_var(--jelly-gloss-top)]">
      <span className="text-sm font-semibold">
        {toPersianDigits(selectedCount)} مورد انتخاب شده
      </span>
      <div className="flex gap-2">
        {actions.map((action) => (
          <Button
            key={action.id}
            size="sm"
            variant={action.variant || 'ghost'}
            onClick={() => onAction(action.id)}
          >
            {action.icon && <Icon name={action.icon} size={14} />}
            {action.label}
          </Button>
        ))}
      </div>
      <button
        onClick={onClear}
        className="mr-auto text-sm text-muted hover:text-text"
      >
        <Icon name="x" size={16} />
      </button>
    </div>
  )
}

function TableFilters({ columns, filters, onFilter }) {
  const filterableColumns = columns.filter((c) => c.filterable)

  if (filterableColumns.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {filterableColumns.map((col) => (
        <input
          key={col.key}
          type="text"
          placeholder={`فیلتر ${col.label}...`}
          value={filters[col.key] || ''}
          onChange={(e) => onFilter({ ...filters, [col.key]: e.target.value })}
          className="min-h-9 w-40 rounded-capsule border border-jelly-rim bg-layer-0 px-3 py-1.5 text-sm shadow-sunken transition-[border-color,box-shadow] duration-200 hover:border-jelly-rim-strong focus:border-jelly-rim-strong focus:shadow-focus focus:outline-none"
        />
      ))}
    </div>
  )
}

function Pagination({ total, page, pageSize, onPageChange }) {
  const totalPages = Math.ceil(total / pageSize)
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  if (totalPages <= 1) return null

  return (
    <div className="mt-4 flex items-center justify-between">
      <div className="text-sm text-muted">
        نمایش {toPersianDigits(start)} تا {toPersianDigits(end)} از{' '}
        {toPersianDigits(total)} مورد
      </div>
      <div className="flex gap-1">
        <Button
          size="sm"
          variant="ghost"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
        >
          <Icon name="chevron-right" size={16} />
        </Button>

        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
          let pageNum
          if (totalPages <= 5) {
            pageNum = i + 1
          } else if (page <= 3) {
            pageNum = i + 1
          } else if (page >= totalPages - 2) {
            pageNum = totalPages - 4 + i
          } else {
            pageNum = page - 2 + i
          }

          return (
            <Button
              key={pageNum}
              size="sm"
              variant={page === pageNum ? 'primary' : 'ghost'}
              onClick={() => onPageChange(pageNum)}
            >
              {toPersianDigits(pageNum)}
            </Button>
          )
        })}

        <Button
          size="sm"
          variant="ghost"
          disabled={page === totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          <Icon name="chevron-left" size={16} />
        </Button>
      </div>
    </div>
  )
}

export default function DataTable({
  columns = [],
  data = [],
  sort,
  onSort,
  filters = {},
  onFilter,
  onEdit,
  bulkActions = [],
  onBulkAction,
  selectable = false,
  editable = false,
  loading = false,
  pagination,
  compact = false,
  onRowClick,
  className = '',
}) {
  const [selected, setSelected] = useState(new Set())
  const [columnVisibility, setColumnVisibility] = useState({})
  const [editingCell, setEditingCell] = useState(null)

  const visibleColumns = useMemo(
    () => columns.filter((c) => columnVisibility[c.key] !== false),
    [columns, columnVisibility]
  )

  const toggleSelect = (id) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelected(newSelected)
  }

  const toggleSelectAll = () => {
    if (selected.size === data.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(data.map((row) => row.id)))
    }
  }

  const handleCellEdit = async (rowId, colKey, value) => {
    setEditingCell(null)
    if (onEdit) {
      await onEdit(rowId, colKey, value)
    }
  }

  const handleBulkAction = (actionId) => {
    if (onBulkAction) {
      onBulkAction(actionId, Array.from(selected))
    }
  }

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          {/* Column visibility */}
          <ColumnVisibilityMenu
            columns={columns}
            visibility={columnVisibility}
            onChange={setColumnVisibility}
          />

          {/* Bulk actions */}
          {selectable && selected.size > 0 && bulkActions.length > 0 && (
            <BulkActionsToolbar
              selectedCount={selected.size}
              actions={bulkActions}
              onAction={handleBulkAction}
              onClear={() => setSelected(new Set())}
            />
          )}
        </div>

        {/* Filters */}
        {onFilter && (
          <TableFilters columns={columns} filters={filters} onFilter={onFilter} />
        )}
      </div>

      {/* Table */}
      <div className={tw.tableWrap}>
        <table className={cn(tw.table, compact && tw.tableCompact)}>
          <thead>
            <tr>
              {selectable && (
                <th style={{ width: '48px' }}>
                  <input
                    type="checkbox"
                    checked={selected.size === data.length && data.length > 0}
                    onChange={toggleSelectAll}
                    className="h-4 w-4 accent-accent"
                  />
                </th>
              )}
              {visibleColumns.map((col) => (
                <th key={col.key} style={col.width ? { width: col.width } : undefined}>
                  {col.sortable && onSort ? (
                    <button
                      onClick={() => onSort(col.key)}
                      className="flex items-center gap-1.5 font-inherit text-inherit hover:text-text"
                    >
                      {col.label}
                      <SortIcon
                        direction={sort?.key === col.key ? sort.direction : null}
                      />
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={visibleColumns.length + (selectable ? 1 : 0)}>
                  <div className="py-10 text-center text-sm text-muted">
                    در حال بارگذاری...
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={visibleColumns.length + (selectable ? 1 : 0)}>
                  <div className="py-10 text-center text-sm text-muted">
                    داده‌ای برای نمایش وجود ندارد.
                  </div>
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr
                  key={row.id || idx}
                  className={cn(
                    onRowClick && 'cursor-pointer',
                    selected.has(row.id) && 'bg-layer-1'
                  )}
                  onClick={() => onRowClick && onRowClick(row)}
                >
                  {selectable && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(row.id)}
                        onChange={() => toggleSelect(row.id)}
                        className="h-4 w-4 accent-accent"
                      />
                    </td>
                  )}
                  {visibleColumns.map((col) => {
                    const cellKey = `${row.id}-${col.key}`
                    const isEditing = editingCell === cellKey

                    return (
                      <td
                        key={col.key}
                        onClick={(e) => {
                          if (editable && col.editable) {
                            e.stopPropagation()
                          }
                        }}
                      >
                        {editable && col.editable && isEditing ? (
                          <input
                            type="text"
                            defaultValue={row[col.key]}
                            onBlur={(e) =>
                              handleCellEdit(row.id, col.key, e.target.value)
                            }
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleCellEdit(row.id, col.key, e.target.value)
                              } else if (e.key === 'Escape') {
                                setEditingCell(null)
                              }
                            }}
                            autoFocus
                            className="w-full min-w-0 rounded border border-accent bg-layer-0 px-2 py-1 text-sm outline-none"
                          />
                        ) : (
                          <div
                            onDoubleClick={() => {
                              if (editable && col.editable && !onRowClick) {
                                setEditingCell(cellKey)
                              }
                            }}
                            className={cn(
                              editable && col.editable && 'cursor-text'
                            )}
                          >
                            {col.render ? col.render(row) : row[col.key]}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pagination && (
        <Pagination
          total={pagination.total}
          page={pagination.page}
          pageSize={pagination.pageSize}
          onPageChange={pagination.onPageChange}
        />
      )}
    </div>
  )
}
