// صفحه مدیریت اسناد حسابداری

import { useState, useEffect, useCallback } from 'react'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import DocumentForm from '../components/accounting/DocumentForm'
import { useCompactAccountingTable } from '../hooks/useCompactAccountingTable'
import { Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { hasPermission } from '../utils/permissions'
import AutoDocumentsWorkspace from '../accounting/AutoDocumentsWorkspace'

export default function AccountingDocuments() {
  const { user } = useAuth()
  const compactView = useCompactAccountingTable()
  const [showForm, setShowForm] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [accountGroups, setAccountGroups] = useState([])
  const [subsidiaries, setSubsidiaries] = useState([])
  const [details, setDetails] = useState([])
  const [reloadToken, setReloadToken] = useState(0)

  const api = accountingApi
  const canApprove = hasPermission(user, 'approve_accounting')

  const refresh = useCallback(() => setReloadToken((token) => token + 1), [])

  const loadMetadata = useCallback(async () => {
    try {
      const [accounts, subs, dets] = await Promise.all([
        api.accounts(),
        api.subsidiaries(),
        api.details(),
      ])
      setAccountGroups(resultList(accounts))
      setSubsidiaries(resultList(subs))
      setDetails(resultList(dets))
    } catch (err) {
      console.error('خطا در بارگذاری metadata:', err)
    }
  }, [api])

  useEffect(() => {
    const timeoutId = setTimeout(loadMetadata, 0)
    return () => clearTimeout(timeoutId)
  }, [loadMetadata])

  const handleCreateNew = () => {
    setSelectedDoc(null)
    setShowForm(true)
  }

  const handleEdit = async (doc) => {
    setSelectedDoc(doc)
    setShowForm(true)
    try {
      setSelectedDoc(await api.getDocument(doc.document_code))
    } catch {
      setSelectedDoc(doc)
    }
  }

  const handleSave = async (formData) => {
    try {
      if (selectedDoc) {
        await api.updateDocument(selectedDoc.document_code, formData)
      } else {
        await api.createDocument(formData)
      }
      setShowForm(false)
      refresh()
    } catch (err) {
      alert('خطا در ذخیره سند: ' + err.message)
    }
  }

  const handleSubmit = async (formData) => {
    try {
      if (selectedDoc) {
        await api.submitDocument(selectedDoc.document_code)
      } else {
        const created = await api.createDocument(formData)
        await api.submitDocument(created.document_code)
      }
      setShowForm(false)
      refresh()
    } catch (err) {
      alert('خطا در ارسال سند: ' + err.message)
    }
  }

  const handleApprove = async (documentCode) => {
    try {
      await api.approveDocument(documentCode, true)
      refresh()
      setShowForm(false)
    } catch (err) {
      alert('خطا در تایید سند: ' + err.message)
    }
  }

  const handleReject = async (documentCode) => {
    try {
      await api.approveDocument(documentCode, false)
      refresh()
      setShowForm(false)
    } catch (err) {
      alert('خطا در رد سند: ' + err.message)
    }
  }

  const handleDelete = async (documentCode) => {
    if (!confirm('آیا از حذف این سند مطمئن هستید؟')) return
    try {
      await api.deleteDocument(documentCode)
      refresh()
    } catch (err) {
      alert('خطا در حذف سند: ' + err.message)
    }
  }

  return (
    <>
      <AutoDocumentsWorkspace
        api={api}
        compact={compactView}
        reloadToken={reloadToken}
        onCreate={handleCreateNew}
        onOpen={handleEdit}
        onDelete={handleDelete}
      />

      <Modal
        title={selectedDoc ? `سند ${selectedDoc.document_code}` : 'سند جدید'}
        open={showForm}
        onClose={() => setShowForm(false)}
        className="acct-document-modal"
        overlayClassName="acct-document-modal-overlay"
      >
        <DocumentForm
          document={selectedDoc}
          onSave={handleSave}
          onSubmit={handleSubmit}
          onApprove={() => handleApprove(selectedDoc?.document_code)}
          onReject={(reason) => handleReject(selectedDoc?.document_code, reason)}
          accountGroups={accountGroups}
          subsidiaries={subsidiaries}
          details={details}
          canApprove={canApprove}
          readOnly={selectedDoc?.status === 'posted'}
        />
      </Modal>
    </>
  )
}
