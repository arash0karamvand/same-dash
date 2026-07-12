// چارت سازمانی — نقش‌ها، شعب و سلسله‌مراتب

import { useCallback, useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { Badge, Card, EmptyState, StatCard } from '../components/ui'

function OrgNode({ node, depth = 0 }) {
  return (
    <div className="org-node-wrap" style={{ '--depth': depth }}>
      <div className="org-node" style={{ borderColor: node.role_color }}>
        <div className="org-node-name">{node.full_name}</div>
        <div className="org-node-meta">
          <Badge color={node.role_color}>{node.role_label}</Badge>
          {node.org_rank && <span className="org-rank-tag" style={{ background: node.org_rank_color }}>{node.org_rank}</span>}
        </div>
        {node.job_title && <div className="muted small">{node.job_title}</div>}
        <div className="muted small">{node.branch_label}</div>
      </div>
      {node.children?.length > 0 && (
        <div className="org-children">
          {node.children.map((child) => (
            <OrgNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function OrgChart() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [view, setView] = useState('tree')

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

  if (loading) return <div className="page"><p className="muted">در حال بارگذاری چارت…</p></div>
  if (error) return <div className="page"><div className="alert-error">{error}</div></div>
  if (!data) return null

  return (
    <div className="page org-chart-page">
      <div className="stat-grid">
        <StatCard label="پرسنل فعال" value={data.stats.total_staff} accent="#6366f1" />
        <StatCard label="شعب" value={data.stats.branches} accent="#10b981" />
        <StatCard label="مدیران" value={data.stats.managers} accent="#f59e0b" />
      </div>

      <Card
        title="چارت سازمانی"
        actions={(
          <div className="org-view-toggle">
            <button type="button" className={view === 'tree' ? 'active' : ''} onClick={() => setView('tree')}>درختی</button>
            <button type="button" className={view === 'branch' ? 'active' : ''} onClick={() => setView('branch')}>بر اساس شعبه</button>
            <button type="button" className={view === 'roles' ? 'active' : ''} onClick={() => setView('roles')}>سلسله نقش‌ها</button>
          </div>
        )}
      >
        {view === 'tree' && (
          data.tree.length === 0 ? (
            <EmptyState message="هنوز سلسله‌مراتب تعریف نشده — در ویرایش کاربر، «مدیر مستقیم» را تنظیم کنید." />
          ) : (
            <div className="org-tree">
              {data.tree.map((node) => (
                <OrgNode key={node.id} node={node} />
              ))}
            </div>
          )
        )}

        {view === 'branch' && (
          <div className="org-branch-grid">
            {data.by_branch.map((b) => (
              <div key={b.branch} className="org-branch-card">
                <h3>{b.label}</h3>
                <ul>
                  {b.members.map((m) => (
                    <li key={m.id}>
                      <strong>{m.full_name}</strong>
                      <span className="muted"> — {m.role_label}</span>
                      {m.job_title && <span className="muted"> ({m.job_title})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {view === 'roles' && (
          <div className="org-role-ladder">
            {data.role_hierarchy.map((r) => {
              const parent = data.role_hierarchy.find((x) => x.slug === r.parent_slug)
              return (
                <div key={r.slug} className="org-role-step" style={{ borderRightColor: r.color }}>
                  <Badge color={r.color}>{r.label}</Badge>
                  {parent && <span className="muted small"> زیرمجموعه {parent.label}</span>}
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
