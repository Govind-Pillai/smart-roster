import { useState, useMemo } from 'react'
import { getDateArray, statusColor, statusShort } from '../../utils/dateUtils'
import CellEditPopover from '../modals/CellEditPopover'
import Badge from '../ui/Badge'

export default function PodWiseView({
  rosterData, employees, pods, year, month,
  conflicts, onCellEdit, brands, processes,
}) {
  const [popover, setPopover] = useState(null)
  const [collapsedPods, setCollapsedPods] = useState({})
  const dateArray = useMemo(() => getDateArray(year, month), [year, month])

  const entryMap = useMemo(() => {
    const map = {}
    rosterData.forEach(entry => {
      const eid = entry.employee_id || entry.employee
      if (!map[eid]) map[eid] = {}
      map[eid][entry.date] = entry
    })
    return map
  }, [rosterData])

  const conflictSet = useMemo(() => {
    const s = new Set()
    conflicts.forEach(c => { if (c.employee_id && c.date) s.add(`${c.employee_id}|${c.date}`) })
    return s
  }, [conflicts])

  const podGroups = useMemo(() => {
    return pods.map(pod => ({
      pod,
      members: employees.filter(e => (e.pod_id || e.pod) === pod.id),
    })).filter(g => g.members.length > 0)
  }, [pods, employees])

  const getPodStats = (members, today) => {
    const todayStr = today.toISOString().slice(0, 10)
    const working = members.filter(e => entryMap[e.id]?.[todayStr]?.status === 'WORKING').length
    const onLeave = members.filter(e => {
      const s = entryMap[e.id]?.[todayStr]?.status
      return s === 'PLANNED_LEAVE' || s === 'COMP_OFF'
    }).length
    return { total: members.length, working, onLeave }
  }

  const getBrandAbbrv = (entry) => {
    if (!entry || entry.status !== 'WORKING') return ''
    const brand = brands.find(b => b.id === (entry.brand_id || entry.brand))
    return brand?.abbreviation || brand?.name?.slice(0, 3) || ''
  }

  const today = new Date()

  const handleCellClick = (e, emp, dateInfo) => {
    const entry = entryMap[emp.id]?.[dateInfo.date]
    setPopover({
      entryId: entry?.id,
      employeeId: emp.id,
      date: dateInfo.date,
      status: entry?.status || 'WORKING',
      brandId: entry?.brand_id || entry?.brand || '',
      processId: entry?.process_id || entry?.process || '',
    })
  }

  return (
    <div className="space-y-4">
      {popover && (
        <CellEditPopover
          {...popover}
          brands={brands}
          processes={processes}
          onSave={(updates) => {
            onCellEdit(popover.entryId, { ...updates, date: popover.date, employee: popover.employeeId })
            setPopover(null)
          }}
          onClose={() => setPopover(null)}
        />
      )}

      {podGroups.length === 0 && (
        <div className="text-center py-16 text-gray-400">No pods configured yet.</div>
      )}

      {podGroups.map(({ pod, members }) => {
        const stats = getPodStats(members, today)
        const isCollapsed = collapsedPods[pod.id]
        const utilPct = stats.total > 0 ? Math.round((stats.working / stats.total) * 100) : 0

        return (
          <div key={pod.id} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Pod header */}
            <div
              className="flex items-center gap-4 px-4 py-3 bg-gradient-to-r from-blue-50 to-white border-b border-gray-200 cursor-pointer hover:bg-blue-50/70 transition-colors"
              onClick={() => setCollapsedPods(prev => ({ ...prev, [pod.id]: !prev[pod.id] }))}
            >
              <div className="flex items-center gap-2 flex-1">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="font-semibold text-gray-800">{pod.name}</span>
                {pod.lead_name && (
                  <span className="text-xs text-gray-500">Lead: {pod.lead_name}</span>
                )}
              </div>
              {/* Stats */}
              <div className="flex items-center gap-4 text-sm">
                <Badge variant="primary">{stats.total} total</Badge>
                <Badge variant="success">{stats.working} working</Badge>
                {stats.onLeave > 0 && <Badge variant="warning">{stats.onLeave} on leave</Badge>}
              </div>
              {/* Utilization bar */}
              <div className="flex items-center gap-2 w-28">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${utilPct >= 80 ? 'bg-green-500' : utilPct >= 50 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${utilPct}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-8">{utilPct}%</span>
              </div>
              <span className="text-gray-400 text-sm">{isCollapsed ? '▶' : '▼'}</span>
            </div>

            {/* Matrix for this pod */}
            {!isCollapsed && (
              <div className="overflow-x-auto scrollbar-thin">
                <table className="text-xs border-collapse min-w-full">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="sticky left-0 z-10 bg-gray-50 border-b border-r border-gray-200 px-3 py-1.5 text-left font-medium text-gray-600 min-w-[140px]">Employee</th>
                      {dateArray.map(d => (
                        <th key={d.date} className={`border-b border-gray-200 px-0.5 py-1 text-center min-w-[32px] w-8 ${d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-400' : 'text-gray-500'}`}>
                          <div>{d.day}</div>
                          <div className="text-[9px] text-gray-400">{d.dayLabel}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((emp, ri) => (
                      <tr key={emp.id} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                        <td className="sticky left-0 z-10 border-b border-r border-gray-200 px-3 py-1.5 bg-inherit">
                          <span className="font-medium text-gray-800 truncate block max-w-[130px]">{emp.name}</span>
                        </td>
                        {dateArray.map(d => {
                          const entry = entryMap[emp.id]?.[d.date]
                          const hasConflict = conflictSet.has(`${emp.id}|${d.date}`)
                          const colorClass = entry ? statusColor(entry.status) : (d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-300' : 'bg-gray-50 text-gray-300')
                          const abbr = getBrandAbbrv(entry)
                          return (
                            <td
                              key={d.date}
                              onClick={(e) => handleCellClick(e, emp, d)}
                              className="border-b border-gray-100 p-0.5 text-center cursor-pointer hover:opacity-75 transition-opacity"
                            >
                              <div className={`rounded px-0.5 py-0.5 text-[10px] font-medium leading-tight ${colorClass} ${hasConflict ? 'ring-2 ring-red-400 ring-inset' : ''}`}>
                                {abbr || (entry ? statusShort(entry.status) : '')}
                              </div>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
