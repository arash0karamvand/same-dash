import { AccountingDataPanel, AccountingPageHeader, AccountingPagination, AccountingSummary } from '../components/accounting/AccountingERP'
import TableViewToggle from '../components/accounting/TableViewToggle'
import { Button } from '../components/ui'
import Icon from '../components/icons/Icon'
import { fromLegacy } from '../styles/tw'
import { formatRial } from '../utils/format'
import AutoDocumentFilters from './AutoDocumentFilters'
import AutoDocumentGrid from './AutoDocumentGrid'
import JournalLineGrid from './JournalLineGrid'
import { useDocumentBoard } from './useDocumentBoard'
import type { AccountingDocument } from './types'

type DocumentsApi = {
  listDocuments: (opts: Record<string, string | number>) => Promise<unknown>
  getDocument: (code: string) => Promise<unknown>
}

type Props = {
  api: DocumentsApi
  compact: boolean
  reloadToken?: number
  onCreate: () => void
  onOpen: (doc: AccountingDocument) => void
  onDelete: (code: string) => void
}

export default function AutoDocumentsWorkspace({
  api,
  compact,
  reloadToken = 0,
  onCreate,
  onOpen,
  onDelete,
}: Props) {
  const { state, dispatch, pageSize } = useDocumentBoard(api, reloadToken)
  const tone = state.pageTotals.balanced ? 'success' : 'warning'

  return (
    <div className={fromLegacy('accounting-documents-page')}>
      <AccountingPageHeader
        eyebrow="اسناد خودکار"
        title="اسناد صادرشده از انبار، فروش و کارخانه"
        description="فیلتر بر اساس تاریخ، ماژول مبدا و شماره سند. جمع بدهکار و بستانکار هر صفحه جدا نگه داشته می‌شود."
        actions={(
          <>
            <TableViewToggle showPrint />
            <Button variant="primary" onClick={onCreate}>
              <Icon name="plus" size={16} />
              <span>ثبت سند جدید</span>
            </Button>
          </>
        )}
      />

      <AccountingDataPanel className="acct-erp-filters-panel">
        <AutoDocumentFilters
          filters={state.draft}
          onChange={(patch) => dispatch({ type: 'patch', patch })}
          onApply={() => dispatch({ type: 'apply' })}
          onReset={() => dispatch({ type: 'reset' })}
        />
      </AccountingDataPanel>

      <AccountingSummary items={[
        { label: 'بدهکار صفحه', value: formatRial(state.pageTotals.debit) },
        { label: 'بستانکار صفحه', value: formatRial(state.pageTotals.credit) },
        {
          label: 'اختلاف صفحه',
          value: formatRial(Math.abs(state.pageTotals.difference)),
          tone,
        },
      ]} />

      <AccountingDataPanel
        title="فهرست اسناد"
        subtitle={`${state.total.toLocaleString('fa-IR')} سند مطابق فیلتر`}
      >
        <AutoDocumentGrid
          rows={state.rows}
          loading={state.loading}
          error={state.error}
          selectedCode={state.selectedCode}
          compact={compact}
          totals={state.pageTotals}
          onSelect={(code) => dispatch({ type: 'select', code })}
          onOpen={onOpen}
          onDelete={onDelete}
        />
        <AccountingPagination
          page={state.page}
          pageSize={pageSize}
          total={state.total}
          onPageChange={(page: number) => dispatch({ type: 'page', page })}
          disabled={state.loading}
        />
      </AccountingDataPanel>

      <JournalLineGrid
        document={state.detail}
        rows={state.lineRows}
        totals={state.lineTotals}
        loading={state.detailLoading}
      />
    </div>
  )
}
