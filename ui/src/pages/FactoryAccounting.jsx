import Accounting from './Accounting'
import { factoryAccountingApi } from '../api/client'

export default function FactoryAccounting() {
  return (
    <Accounting
      api={factoryAccountingApi}
      pageTitle="حسابداری کارخانه"
      createPermission="create_factory_accounting"
      editPermission="edit_factory_accounting"
      deletePermission="delete_factory_accounting"
      approvePermission="approve_factory_accounting"
      guidePrefix="factory-accounting"
      ledgerKind="factory"
      transferPermission="transfer_factory_accounting_to_office"
    />
  )
}
