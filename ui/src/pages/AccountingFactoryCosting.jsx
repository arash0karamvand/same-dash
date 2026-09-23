// صفحه بهای تمام‌شده کارخانه

import { useState, useEffect, useCallback } from 'react'
import { accountingApi, productsApi } from '../api/client'
import { resultList } from '../api/accounting'
import CostCentersManager from '../components/accounting/CostCentersManager'
import OverheadAllocation from '../components/accounting/OverheadAllocation'
import WIPClosePanel from '../components/accounting/WIPClosePanel'
import SpoilageReport from '../components/accounting/SpoilageReport'
import { AccountingDataPanel, AccountingPageHeader, AccountingSummary } from '../components/accounting/AccountingERP'
import { Button, Field } from '../components/ui'
import PersianDateInput from '../components/PersianDateInput'
import Icon from '../components/icons/Icon'
import { fromLegacy } from '../styles/tw'

export default function AccountingFactoryCosting({ tab = 'cost-centers' }) {
  const [costCenters, setCostCenters] = useState([])
  const [overheadPeriods, setOverheadPeriods] = useState([])
  const [wipCloses, setWipCloses] = useState([])
  const [spoilageData, setSpoilageData] = useState([])
  const [products, setProducts] = useState([])
  const [spoilageFilters, setSpoilageFilters] = useState({
    dateFrom: '',
    dateTo: '',
  })
  const [loading, setLoading] = useState(false)

  const loadCostCenters = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.costCenters()
      setCostCenters(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری مراکز هزینه:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadOverhead = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.overheadPeriods()
      setOverheadPeriods(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری دوره‌های سربار:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadWipCloses = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.wipCloses()
      setWipCloses(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری WIP:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSpoilage = useCallback(async () => {
    setLoading(true)
    try {
      const result = await accountingApi.spoilage(spoilageFilters)
      setSpoilageData(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری ضایعات:', err)
    } finally {
      setLoading(false)
    }
  }, [spoilageFilters])

  const loadProducts = useCallback(async () => {
    try {
      const result = await productsApi.list({ limit: 1000 })
      setProducts(resultList(result))
    } catch (err) {
      console.error('خطا در بارگذاری محصولات:', err)
    }
  }, [])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadProducts()
      loadCostCenters()
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [loadProducts, loadCostCenters])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (tab === 'overhead') loadOverhead()
      else if (tab === 'wip-close') loadWipCloses()
      else if (tab === 'spoilage') loadSpoilage()
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [tab, loadOverhead, loadWipCloses, loadSpoilage])

  const handleSaveCostCenter = async (data, id) => {
    if (id) {
      await accountingApi.updateCostCenter(id, data)
    } else {
      await accountingApi.saveCostCenter(data)
    }
    loadCostCenters()
  }

  const handleSaveOverhead = async (data) => {
    await accountingApi.saveOverhead(data)
    loadOverhead()
  }

  const handleAllocateOverhead = async (periodId) => {
    await accountingApi.allocateOverhead(periodId)
    loadOverhead()
  }

  const handleSaveWipClose = async (data) => {
    await accountingApi.saveWipClose(data)
    loadWipCloses()
  }

  return (
    <div className={fromLegacy('accounting-factory-costing-page')}>
      <AccountingPageHeader
        eyebrow="کنترل تولید"
        title={{
          'cost-centers': 'مراکز هزینه',
          overhead: 'تسهیم سربار',
          'wip-close': 'بستن کالای در جریان ساخت',
          spoilage: 'کنترل ضایعات',
        }[tab] || 'بهای تمام‌شده'}
        description="محاسبه و کنترل هزینه تولید از مرکز هزینه تا محصول نهایی"
      />

      <AccountingSummary items={[
        { label: 'مراکز هزینه', value: costCenters.length.toLocaleString('fa-IR') },
        { label: 'دوره‌های سربار', value: overheadPeriods.length.toLocaleString('fa-IR') },
        { label: 'دوره‌های بسته‌شده WIP', value: wipCloses.length.toLocaleString('fa-IR') },
      ]} />

      {tab === 'cost-centers' && (
        <CostCentersManager
          costCenters={costCenters}
          onSave={handleSaveCostCenter}
          onRefresh={loadCostCenters}
          loading={loading}
        />
      )}

      {tab === 'overhead' && (
        <OverheadAllocation
          periods={overheadPeriods}
          costCenters={costCenters}
          onSave={handleSaveOverhead}
          onAllocate={handleAllocateOverhead}
          loading={loading}
        />
      )}

      {tab === 'wip-close' && (
        <WIPClosePanel
          wipCloses={wipCloses}
          products={products}
          onSave={handleSaveWipClose}
          loading={loading}
        />
      )}

      {tab === 'spoilage' && (
        <>
          <AccountingDataPanel title="فیلتر گزارش ضایعات">
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
              <Field label="از تاریخ">
                <PersianDateInput
                  value={spoilageFilters.dateFrom}
                  onChange={(val) => setSpoilageFilters({ ...spoilageFilters, dateFrom: val })}
                />
              </Field>
              <Field label="تا تاریخ">
                <PersianDateInput
                  value={spoilageFilters.dateTo}
                  onChange={(val) => setSpoilageFilters({ ...spoilageFilters, dateTo: val })}
                />
              </Field>
              <Button variant="primary" onClick={loadSpoilage}>
                <Icon name="search" size={16} />
                <span>جستجو</span>
              </Button>
            </div>
          </AccountingDataPanel>
          <SpoilageReport spoilageData={spoilageData} loading={loading} />
        </>
      )}
    </div>
  )
}
