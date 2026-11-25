import { useMemo } from 'react'
import { getDateArray, statusColor, statusShort, MONTHS } from '../../utils/dateUtils'
import Select from '../ui/Select'
import Badge from '../ui/Badge'

const STATUS_LABELS = {
  WORKING: { label: 'Working', variant: 'primary' },
  WEEKLY_OFF: { label: 'Weekly Off', variant: 'default' },
  PUBLIC_HOLIDAY: { label: 'Public Holiday', variant: 'purple' },
  PLANNED_LEAVE: { label: 'Planned Leave', variant: 'warning' },
  COMP_OFF: { label: 'Comp Off', variant: 'teal' },
}

export default function EmployeeWiseView({
  rosterData, employees, pods, year, month,
  selectedEmployee, setSelectedEmployee, conflicts,
}) {
  const dateArray = useMemo(() => getDateArray(year, month), [year, month])

  const empOptions = useMemo(() => [
    { value: '', label: 'Select an employee…' },
    ...employees.map(e => ({ value: String(e.id), label: e.name })),
  ], [employees])

  const emp = useMemo(() => employees.find(e => String(e.id) === String(selectedEmployee)), [employees, selectedEmployee])

  const empEntries = useMemo(() => {
    if (!emp) return {}
    const map = {}
    rosterData.filter(e => (e.employee_id || e.employee) === emp.id).forEach(e => { map[e.date] = e })
    return map
  }, [rosterData, emp])

  const empConflicts = useMemo(() => {
    if (!emp) return []
    return conflicts.filter(c => c.employee_id === emp.id && !c.resolved)
  }, [conflicts, emp])

  const stats = useMemo(() => {
    const counts = { WORKING: 0, WEEKLY_OFF: 0, PUBLIC_HOLIDAY: 0, PLANNED_LEAVE: 0, COMP_OFF: 0 }
    Object.values(empEntries).forEach(e => { if (counts[e.status] !== undefined) counts[e.status]++ })
    return counts
  }, [empEntries])

  const pod = emp ? pods.find(p => p.id === (emp.pod_id || emp.pod)) : null

  return (
    <div className="space-y-4">
      {/* Employee selector */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex-1 min-w-48">
            <label className="block text-xs font-medium text-gray-500 mb-1">Select Employee</label>
            <Select
              value={String(selectedEmployee || '')}
              onChange={v => setSelectedEmployee(v ? Number(v) : null)}
              options={empOptions}
              className="w-full"
            />
          </div>
          {emp && (
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <div>
                <div className="text-xs text-gray-400">Pod</div>
                <div className="font-medium">{pod?.name || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Month</div>
                <div className="font-medium">{MONTHS[month - 1]} {year}</div>
              </div>
              {empConflicts.length > 0 && (
                <Badge variant="danger">{empConflicts.length} conflict{empConflicts.length !== 1 ? 's' : ''}</Badge>
              )}
            </div>
          )}
        </div>
      </div>

      {!emp && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg font-medium">Select an employee above</p>
          <p className="text-sm mt-1">View their monthly schedule, stats, and conflicts</p>
        </div>
      )}

      {emp && (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(STATUS_LABELS).map(([status, { label, variant }]) => (
              <div key={status} className="bg-white rounded-xl border border-gray-200 shadow-sm p-3 text-center">
                <div className="text-2xl font-bold text-gray-800">{stats[status]}</div>
                <Badge variant={variant} className="mt-1">{label}</Badge>
              </div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h3 className="font-semibold text-gray-800">{emp.name} — {MONTHS[month - 1]} {year}</h3>
            </div>
            <div className="p-4">
              {/* Day headers */}
              <div className="grid grid-cols-7 gap-1 mb-1">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => (
                  <div key={d} className="text-center text-xs font-medium text-gray-500 py-1">{d}</div>
                ))}
              </div>
              {/* Calendar cells */}
              {(() => {
                // Pad to start on Monday
                const firstDay = dateArray[0]
                const pad = (firstDay.dayOfWeek + 6) % 7 // Mon=0
                const cells = [...Array(pad).fill(null), ...dateArray]
                const rows = []
                for (let i = 0; i < cells.length; i += 7) {
                  rows.push(cells.slice(i, i + 7))
                }
                return rows.map((row, ri) => (
                  <div key={ri} className="grid grid-cols-7 gap-1 mb-1">
                    {row.map((d, ci) => {
                      if (!d) return <div key={ci} />
                      const entry = empEntries[d.date]
                      const hasConflict = empConflicts.some(c => c.date === d.date)
                      const colorClass = entry ? statusColor(entry.status) : (d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-400' : 'bg-gray-50 text-gray-400')
                      return (
                        <div
                          key={d.date}
                          className={`rounded-lg p-1.5 text-center border ${colorClass} ${hasConflict ? 'ring-2 ring-red-400' : ''}`}
                          title={`${d.date}: ${entry?.status || 'No data'}`}
                        >
                          <div className="text-sm font-semibold">{d.day}</div>
                          <div className="text-[9px] mt-0.5 leading-tight">
                            {entry ? statusShort(entry.status) : '—'}
                          </div>
                        </div>
                      )
                    })}
                    {/* Fill trailing empties */}
                    {Array(7 - row.length).fill(null).map((_, ci) => <div key={`trail-${ci}`} />)}
                  </div>
                ))
              })()}
            </div>
          </div>

          {/* Conflicts for this employee */}
          {empConflicts.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="font-semibold text-gray-800 mb-3">Active Conflicts</h3>
              <div className="space-y-2">
                {empConflicts.map(c => (
                  <div key={c.id} className={`rounded-lg border p-3 ${c.severity === 'CRITICAL' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={c.severity === 'CRITICAL' ? 'danger' : 'warning'}>{c.severity}</Badge>
                      <span className="text-xs text-gray-500">{c.date}</span>
                    </div>
                    <p className="text-sm text-gray-700">{c.description || c.conflict_type}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
