import { Card } from '../components/ui'
import RecordFilterPanel from '../components/RecordFilterPanel'
import { OFFICE_PORTAL_FILTER } from '../config/recordFilterSections'

export default function RecordFilter({ portal }) {
  const isOffice = portal === 'office'
  const scope = isOffice ? OFFICE_PORTAL_FILTER.scope : undefined
  const title = isOffice ? OFFICE_PORTAL_FILTER.title : 'فیلتر'

  return (
    <div className="page record-filter-page">
      <Card title={title}>
        <RecordFilterPanel scope={scope} liveSearch />
      </Card>
    </div>
  )
}