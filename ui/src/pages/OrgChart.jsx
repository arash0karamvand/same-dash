// چارت سازمانی — نقش‌ها، شعب و سلسله‌مراتب

import { useCallback, useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { Badge, Card, EmptyState, StatCard } from '../components/ui'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { fromLegacy } from '../styles/tw.js'

const DRAG_TYPE = 'application/x-org-node'

function nodeById(flat = []) {
  return Object.fromEntries(flat.map((node) => [node.id, node]))
}

function isDescendantOf(flat, ancestorId, nodeId) {
  const map = nodeById(flat)
  const seen = new Set()
  let current = map[nodeId]
  while (current?.manager_id && !seen.has(current.manager_id)) {
    if (current.manager_id === ancestorId) return true
    seen.add(current.manager_id)
    current = map[current.manager_id]
  }
  return false
}

function wouldCycle(flat, userId, managerId) {
  if (!managerId) return false
  if (userId === managerId) return true
  return isDescendantOf(flat, userId, managerId)
}

function OrgNode({
  node,
  depth = 0,
  canEdit,
  draggingId,
  dropTargetId,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}) {
  const dragging = draggingId === node.id
  const dropTarget = dropTargetId === node.id
  return (
    <div className={fromLegacy('org-node-wrap')} style={{ '--depth': depth }}>
      <div
        className={`${fromLegacy('org-node')}${canEdit ? ' is-editable' : ''}${dragging ? ' is-dragging' : ''}${dropTarget ? ' is-drop-target' : ''}`}
        style={{ borderColor: node.role_color }}
        draggable={canEdit}
        onDragStart={(event) => onDragStart(event, node)}
        onDragOver={(event) => onDragOver(event, node)}
        onDrop={(event) => onDrop(event, node)}
        onDragEnd={onDragEnd}
      >
        <div className={fromLegacy('org-node-name')}>{node.full_name}</div>
        <div className={fromLegacy('org-node-meta')}>
          <Badge color={node.role_color}>{node.role_label}</Badge>
          {node.org_rank && (
            <span className={fromLegacy('org-rank-tag')} style={{ background: node.org_rank_color }}>
              {node.org_rank}
            </span>
          )}
        </div>
        {node.job_title && <div className={fromLegacy('muted small')}>{node.job_title}</div>}
        <div className={fromLegacy('muted small')}>{node.branch_label}</div>
        {canEdit && <div className={fromLegacy('muted small org-node-hint')}>برای زیردست کردن، بکشید و رها کنید</div>}
      </div>
      {node.children?.length > 0 && (
        <div className={fromLegacy('org-children')}>
          {node.children.map((child) => (
            <OrgNode
              key={child.id}
              node={child}
              depth={depth + 1}
              canEdit={canEdit}
              draggingId={draggingId}
              dropTargetId={dropTargetId}
              onDragStart={onDragStart}
              onDragOver={onDragOver}
              onDrop={onDrop}
              onDragEnd={onDragEnd}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function OrgChart() {
  useRegisterPageGuide('orgchart', PAGE_GUIDE_DEFAULTS.orgchart)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [view, setView] = useState('tree')
  const [draggingId, setDraggingId] = useState(null)
  const [dropTargetId, setDropTargetId] = useState(null)
  const [rootDrop, setRootDrop] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await authApi.orgChart()
      setData(res)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const canEdit = Boolean(data?.can_edit)

  const reassign = async (userId, managerId) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await authApi.reassignOrgChart({ user_id: userId, manager_id: managerId })
      setData(res)
      setInfo(managerId ? 'زیردست تنظیم شد.' : 'فرد به ریشه منتقل شد.')
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
      setDraggingId(null)
      setDropTargetId(null)
      setRootDrop(false)
    }
  }

  const onDragStart = (event, node) => {
    if (!canEdit) return
    setDraggingId(node.id)
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(DRAG_TYPE, String(node.id))
    event.dataTransfer.setData('text/plain', String(node.id))
  }

  const onDragOver = (event, node) => {
    if (!canEdit || draggingId == null) return
    if (wouldCycle(data?.flat || [], draggingId, node.id)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    if (dropTargetId !== node.id) setDropTargetId(node.id)
  }

  const onDrop = async (event, node) => {
    event.preventDefault()
    event.stopPropagation()
    const raw = event.dataTransfer.getData(DRAG_TYPE) || event.dataTransfer.getData('text/plain')
    const userId = Number(raw)
    setDropTargetId(null)
    if (!canEdit || !userId || wouldCycle(data?.flat || [], userId, node.id)) return
    if (userId === node.id) return
    await reassign(userId, node.id)
  }

  const onDragEnd = () => {
    setDraggingId(null)
    setDropTargetId(null)
    setRootDrop(false)
  }

  const onRootDragOver = (event) => {
    if (!canEdit || draggingId == null) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    setRootDrop(true)
    setDropTargetId(null)
  }

  const onRootDrop = async (event) => {
    event.preventDefault()
    const raw = event.dataTransfer.getData(DRAG_TYPE) || event.dataTransfer.getData('text/plain')
    const userId = Number(raw)
    setRootDrop(false)
    if (!canEdit || !userId) return
    await reassign(userId, null)
  }

  if (loading) return <div className={fromLegacy('page')}><p className={fromLegacy('muted')}>در حال بارگذاری چارت…</p></div>
  if (error && !data) return <div className={fromLegacy('page')}><div className={fromLegacy('alert-error')}>{error}</div></div>
  if (!data) return null

  return (
    <div className={fromLegacy('page org-chart-page')}>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-info')}>{info}</div>}
      <div className={fromLegacy('stat-grid')}>
        <StatCard label="پرسنل فعال" value={data.stats.total_staff} accent="var(--accent)" />
        <StatCard label="شعب" value={data.stats.branches} accent="var(--success)" />
        <StatCard label="مدیران" value={data.stats.managers} accent="var(--warning)" />
      </div>

      <Card
        title="چارت سازمانی"
        actions={(
          <div className={fromLegacy('org-view-toggle')}>
            <button type="button" className={view === 'tree' ? 'active' : ''} onClick={() => setView('tree')}>درختی</button>
            <button type="button" className={view === 'branch' ? 'active' : ''} onClick={() => setView('branch')}>بر اساس شعبه</button>
            <button type="button" className={view === 'roles' ? 'active' : ''} onClick={() => setView('roles')}>سلسله نقش‌ها</button>
          </div>
        )}
      >
        {view === 'tree' && (
          data.tree.length === 0 ? (
            <EmptyState text="هنوز سلسله‌مراتب تعریف نشده — افراد را بکشید و روی مدیر رها کنید، یا در ویرایش کاربر «مدیر مستقیم» را تنظیم کنید." />
          ) : (
            <div className={fromLegacy('org-tree')}>
              {canEdit && (
                <div
                  className={`org-root-drop${rootDrop ? ' is-drop-target' : ''}`}
                  onDragOver={onRootDragOver}
                  onDragLeave={() => setRootDrop(false)}
                  onDrop={onRootDrop}
                >
                  رها کنید تا بدون مدیر (ریشه) شود
                </div>
              )}
              {data.tree.map((node) => (
                <OrgNode
                  key={node.id}
                  node={node}
                  canEdit={canEdit}
                  draggingId={draggingId}
                  dropTargetId={dropTargetId}
                  onDragStart={onDragStart}
                  onDragOver={onDragOver}
                  onDrop={onDrop}
                  onDragEnd={onDragEnd}
                />
              ))}
            </div>
          )
        )}

        {view === 'branch' && (
          <div className={fromLegacy('org-branch-grid')}>
            {data.by_branch.map((b) => (
              <div key={b.branch} className={fromLegacy('org-branch-card')}>
                <h3>{b.label}</h3>
                <ul>
                  {b.members.map((m) => (
                    <li key={m.id}>
                      <strong>{m.full_name}</strong>
                      <span className={fromLegacy('muted')}> — {m.role_label}</span>
                      {m.job_title && <span className={fromLegacy('muted')}> ({m.job_title})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {view === 'roles' && (
          <div className={fromLegacy('org-role-ladder')}>
            {data.role_hierarchy.map((r) => {
              const parent = data.role_hierarchy.find((x) => x.slug === r.parent_slug)
              return (
                <div key={r.slug} className={fromLegacy('org-role-step')} style={{ borderRightColor: r.color }}>
                  <Badge color={r.color}>{r.label}</Badge>
                  {parent && <span className={fromLegacy('muted small')}> زیرمجموعه {parent.label}</span>}
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
