import OfficeSectionCard from '../components/OfficeSectionCard'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { OFFICE_PORTAL_FILTER } from '../config/recordFilterSections'
import { useRegisterPageGuide } from '../context/PageGuideContext'

export default function RecordFilter({ portal }) {
  const isOffice = portal === 'office'
  useRegisterPageGuide('filter', isOffice ? '' : PAGE_GUIDE_DEFAULTS.filter_managers)

  if (!isOffice) {
    return <div className="page record-filter-page" />
  }

  return (
    <div className="page record-filter-page">
      <OfficeSectionCard section={OFFICE_PORTAL_FILTER} />
    </div>
  )
}
