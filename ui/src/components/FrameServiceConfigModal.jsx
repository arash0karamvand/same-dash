import { useEffect, useMemo, useState } from 'react'
import { framesApi, materialsApi } from '../api/client'
import Select from './Select'
import { PICKER_LIMIT } from '../config/pagination'
import { Button, Field, Modal } from './ui'
import { fromLegacy } from '../styles/tw.js'

function buildDefaultConfig(frame) {
  const template = frame?.service_template
  const components = (template?.components || []).map((c) => {
    const entry = { type: c.component_type, qty: c.default_quantity ?? 1 }
    if (c.component_type === 'three_seater' || c.component_type === 'armchair') {
      entry.back_type = 'fabric'
    } else {
      entry.extra_materials = []
    }
    return entry
  })
  return {
    seat_count: template?.default_seat_count || 8,
    components,
  }
}

function componentLabel(type, frame) {
  const row = frame?.service_template?.components?.find((c) => c.component_type === type)
  return row?.component_type_display || type
}

export default function FrameServiceConfigModal({ open, frame, initialConfig, initialModelId, onClose, onConfirm }) {
  const [frameDetail, setFrameDetail] = useState(frame)
  const [seatCount, setSeatCount] = useState(8)
  const [frameModelId, setFrameModelId] = useState('')
  const [components, setComponents] = useState([])
  const [loading, setLoading] = useState(false)
  const [materials, setMaterials] = useState([])

  useEffect(() => {
    if (!open) return
    materialsApi.list({ limit: PICKER_LIMIT, approved_only: true }).then((data) => {
      setMaterials(data.results || [])
    }).catch(() => setMaterials([]))
  }, [open])

  const materialOptions = useMemo(
    () => materials.map((m) => ({ value: String(m.id), label: `${m.name}${m.color_name ? ` (${m.color_name})` : ''}` })),
    [materials],
  )

  useEffect(() => {
    if (!open || !frame?.id) return
    let cancelled = false
    setLoading(true)
    framesApi.get(frame.id).then((data) => {
      if (cancelled) return
      setFrameDetail(data)
      const cfg = initialConfig?.components?.length ? initialConfig : buildDefaultConfig(data)
      setSeatCount(cfg.seat_count || data.service_template?.default_seat_count || 8)
      setComponents(cfg.components || [])
      setFrameModelId(initialModelId ? String(initialModelId) : '')
      setLoading(false)
    }).catch(() => setLoading(false))
    return () => { cancelled = true }
  }, [open, frame?.id, initialConfig, initialModelId])

  const modelOptions = useMemo(
    () => (frameDetail?.models || []).map((m) => ({ value: String(m.id), label: m.name })),
    [frameDetail],
  )

  const updateComponent = (idx, key, val) => {
    setComponents((rows) => rows.map((c, i) => (i === idx ? { ...c, [key]: val } : c)))
  }

  const addExtraMaterial = (idx) => {
    setComponents((rows) => rows.map((c, i) =>
      i === idx
        ? { ...c, extra_materials: [...(c.extra_materials || []), { material_id: '', qty: '1', unit: 'متر' }] }
        : c,
    ))
  }

  const updateExtraMaterial = (compIdx, matIdx, key, val) => {
    setComponents((rows) => rows.map((c, i) =>
      i === compIdx
        ? {
            ...c,
            extra_materials: c.extra_materials.map((m, j) => (j === matIdx ? { ...m, [key]: val } : m)),
          }
        : c,
    ))
  }

  const handleConfirm = () => {
    if ((frameDetail?.models || []).length > 0 && !frameModelId) return
    onConfirm({
      frame_id: frameDetail.id,
      frame_model_id: frameModelId ? Number(frameModelId) : null,
      frame_config: { seat_count: Number(seatCount) || 8, components },
    })
  }

  const hasBack = (type) => type === 'three_seater' || type === 'armchair'
  const isTable = (type) => type === 'side_table' || type === 'coffee_table'

  return (
    <Modal title="پیکربندی سرویس مبلمان" open={open} onClose={onClose} wide>
      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : (
        <div className={fromLegacy('frame-config-form')}>
          <div className={fromLegacy('form-grid-2')}>
            <Field label="تعداد نفر">
              <input className={fromLegacy('ltr')} type="number" min="1" value={seatCount} onChange={(e) => setSeatCount(e.target.value)} />
            </Field>
            {(frameDetail?.models || []).length > 0 && (
              <Field label="مدل کلاف">
                <Select
                  value={frameModelId}
                  onChange={setFrameModelId}
                  options={[{ value: '', label: 'انتخاب مدل…' }, ...modelOptions]}
                  placeholder="مدل کلاف"
                />
              </Field>
            )}
          </div>

          {components.map((comp, idx) => (
            <div key={comp.type || idx} className={fromLegacy('frame-config-component')}>
              <strong>{componentLabel(comp.type, frameDetail)}</strong>
              <div className={fromLegacy('form-grid-2')}>
                <Field label="تعداد">
                  <input className={fromLegacy('ltr')} type="number" min="0" value={comp.qty} onChange={(e) => updateComponent(idx, 'qty', Number(e.target.value) || 0)} />
                </Field>
                {hasBack(comp.type) && (
                  <Field label="نوع پشت">
                    <Select
                      value={comp.back_type || 'fabric'}
                      onChange={(v) => updateComponent(idx, 'back_type', v)}
                      options={[
                        { value: 'fabric', label: 'پشت پارچه' },
                        { value: 'wood', label: 'پشت چوب' },
                      ]}
                    />
                  </Field>
                )}
              </div>
              {isTable(comp.type) && (
                <div>
                  <Button type="button" variant="ghost" onClick={() => addExtraMaterial(idx)}>+ متریال</Button>
                  {(comp.extra_materials || []).map((mat, matIdx) => (
                    <div key={matIdx} className={fromLegacy('form-grid-2')}>
                      <Field label="متریال">
                        <Select
                          value={String(mat.material_id || '')}
                          onChange={(v) => updateExtraMaterial(idx, matIdx, 'material_id', v ? Number(v) : '')}
                          options={[{ value: '', label: 'انتخاب…' }, ...materialOptions]}
                        />
                      </Field>
                      <Field label="مقدار">
                        <input className={fromLegacy('ltr')} type="number" min="0.001" step="0.001" value={mat.qty} onChange={(e) => updateExtraMaterial(idx, matIdx, 'qty', e.target.value)} />
                      </Field>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={onClose}>انصراف</Button>
            <Button type="button" onClick={handleConfirm}>تایید پیکربندی</Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
