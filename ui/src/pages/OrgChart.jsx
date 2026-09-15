// چارت سازمانی — نقش‌ها، شعب و سلسله‌مراتب

import { useCallback, useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { Badge, Card, EmptyState, StatCard } from '../components/ui'
import { fromLegacy } from '../styles/tw.js'

function OrgNode({ node, depth = 0 }) {
  return (
    <div className={fromLegacy("org-node-wrap")} style={{ '--depth': depth }}>
      <div className={fromLegacy("org-node")} style={{ borderColor: node.role_color }}>
        <div className={fromLegacy("org-node-name")}>{node.full_name}</div>
        <div className={fromLegacy("org-node-meta")}>
          <Badge color={node.role_color}>{node.role_label}</Badge>
          {node.org_rank && <span className={fromLegacy("org-rank-tag")} style={{ background: node.org_rank_color }}>{node.org_rank}</span>}
        </div>
        {node.job_title && <div className={fromLegacy("muted small")}>{node.job_title}</div>}
        <div className={fromLegacy("muted small")}>{node.branch_label}</div>
      </div>
      {node.children?.length > 0 && (
        <div className={fromLegacy("org-children")}>
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

  if (loading) return <div className={fromLegacy("page")}><p className={fromLegacy("muted")}>در حال بارگذاری چارت…</p></div>
  if (error) return <div className={fromLegacy("page")}><div className={fromLegacy("alert-error")}>{error}</div></div>
  if (!data) return null

  return (
    <div className={fromLegacy("page org-chart-page")}>
      <div className={fromLegacy("stat-grid")}>
        <StatCard label="پرسنل فعال" value={data.stats.total_staff} accent="var(--accent)" />
        <StatCard label="شعب" value={data.stats.branches} accent="var(--success)" />
        <StatCard label="مدیران" value={data.stats.managers} accent="var(--warning)" />
      </div>

      <Card
        title="چارت سازمانی"
        actions={(
          <div className={fromLegacy("org-view-toggle")}>
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
            <div className={fromLegacy("org-tree")}>
              {data.tree.map((node) => (
                <OrgNode key={node.id} node={node} />
              ))}
            </div>
          )
        )}

        {view === 'branch' && (
          <div className={fromLegacy("org-branch-grid")}>
            {data.by_branch.map((b) => (
              <div key={b.branch} className={fromLegacy("org-branch-card")}>
                <h3>{b.label}</h3>
                <ul>
                  {b.members.map((m) => (
                    <li key={m.id}>
                      <strong>{m.full_name}</strong>
                      <span className={fromLegacy("muted")}> — {m.role_label}</span>
                      {m.job_title && <span className={fromLegacy("muted")}> ({m.job_title})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {view === 'roles' && (
          <div className={fromLegacy("org-role-ladder")}>
            {data.role_hierarchy.map((r) => {
              const parent = data.role_hierarchy.find((x) => x.slug === r.parent_slug)
              return (
                <div key={r.slug} className={fromLegacy("org-role-step")} style={{ borderRightColor: r.color }}>
                  <Badge color={r.color}>{r.label}</Badge>
                  {parent && <span className={fromLegacy("muted small")}> زیرمجموعه {parent.label}</span>}
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
