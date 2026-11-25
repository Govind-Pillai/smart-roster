import { useState, useMemo } from 'react'
import { getDateArray, statusColor, statusShort } from '../../utils/dateUtils'
import CellEditPopover from '../modals/CellEditPopover'

export default function CompanyWideView({
  rosterData, employees, pods, year, month,
  conflicts, filterPod, filterConflictsOnly, onCellEdit,
  brands, processes,
}) {
  const [popover, setPopover] = useState(null) // { entryId, employeeId, date, status, brandId, processId, x, y }
  const dateArray = useMemo(() => getDateArray(year, month), [year, month])

  // Build a lookup: { employeeId: { date: entry } }
  const entryMap = useMemo(() => {
    const map = {}
    rosterData.forEach(entry => {
      const eid = entry.employee_id || entry.employee
      if (!map[eid]) map[eid] = {}
      map[eid][entry.date] = entry
    })
    return map
  }, [rosterData])

  // Build conflict set: Set of "employeeId|date"
  const conflictSet = useMemo(() => {
    const s = new Set()
    conflicts.forEach(c => {
      if (c.employee_id && c.date) s.add(`${c.employee_id}|${c.date}`)
    })
    return s
  }, [conflicts])

  // Filter employees
  const filteredEmployees = useMemo(() => {
    let emps = employees
    if (filterPod !== 'all') {
      emps = emps.filter(e => String(e.pod_id || e.pod) === filterPod)
    }
    if (filterConflictsOnly) {
      emps = emps.filter(e => {
        return dateArray.some(d => conflictSet.has(`${e.id}|${d.date}`))
      })
    }
    return emps
  }, [employees, filterPod, filterConflictsOnly, dateArray, conflictSet])

  const getPodName = (emp) => {
    const pod = pods.find(p => p.id === (emp.pod_id || emp.pod))
    return pod?.name || ''
  }

  const getBrandAbbrv = (entry) => {
    if (!entry || entry.status !== 'WORKING') return ''
    const brand = brands.find(b => b.id === (entry.brand_id || entry.brand))
    return brand?.abbreviation || brand?.name?.slice(0, 3) || ''
  }

  const handleCellClick = (e, emp, dateInfo) => {
    const entry = entryMap[emp.id]?.[dateInfo.date]
    const rect = e.currentTarget.getBoundingClientRect()
    setPopover({
      entryId: entry?.id,
      employeeId: emp.id,
      date: dateInfo.date,
      status: entry?.status || 'WORKING',
      brandId: entry?.brand_id || entry?.brand || '',
      processId: entry?.process_id || entry?.process || '',
      x: rect.left,
      y: rect.bottom + window.scrollY,
    })
  }

  if (employees.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <p className="text-lg font-medium">No roster data yet</p>
        <p className="text-sm mt-1">Click "Generate Roster" to create the monthly roster</p>
      </div>
    )
  }

  return (
    <div className="relative">
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

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Summary bar */}
        <div className="px-4 py-2 border-b border-gray-100 bg-gray-50 flex items-center gap-6 text-sm text-gray-600">
          <span className="font-medium text-gray-800">Company-Wide Roster</span>
          <span>{filteredEmployees.length} employees</span>
          <span>{dateArray.length} days</span>
          <div className="flex gap-3 ml-auto text-xs">
            {[
              ['W', 'bg-blue-100 text-blue-700', 'Working'],
              ['WO', 'bg-gray-200 text-gray-600', 'Weekly Off'],
              ['PH', 'bg-purple-100 text-purple-700', 'Public Holiday'],
              ['PL', 'bg-amber-100 text-amber-700', 'Planned Leave'],
              ['CO', 'bg-teal-100 text-teal-700', 'Comp Off'],
            ].map(([s, cls, label]) => (
              <span key={s} className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${cls}`} title={label}>
                {s}
              </span>
            ))}
          </div>
        </div>

        {/* Matrix table */}
        <div className="overflow-x-auto scrollbar-thin">
          <table className="text-xs border-collapse min-w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="sticky left-0 z-20 bg-gray-50 border-b border-r border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 min-w-[160px]">
                  Employee
                </th>
                {dateArray.map(d => (
                  <th
                    key={d.date}
                    className={`border-b border-gray-200 px-1 py-1 text-center font-medium min-w-[36px] w-9
                      ${d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-400' : 'text-gray-600'}`}
                  >
                    <div>{d.day}</div>
                    <div className="text-gray-400 font-normal">{d.dayLabel}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredEmployees.map((emp, ri) => (
                <tr key={emp.id} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="sticky left-0 z-10 border-b border-r border-gray-200 px-3 py-1.5 bg-inherit">
                    <div className="font-medium text-gray-800 truncate max-w-[140px]">{emp.name}</div>
                    <div className="text-gray-400 text-[10px] truncate">{getPodName(emp)}</div>
                  </td>
                  {dateArray.map(d => {
                    const entry = entryMap[emp.id]?.[d.date]
                    const hasConflict = conflictSet.has(`${emp.id}|${d.date}`)
                    const colorClass = entry ? statusColor(entry.status) : 'bg-gray-50 text-gray-300'
                    const abbr = getBrandAbbrv(entry)
                    return (
                      <td
                        key={d.date}
                        onClick={(e) => handleCellClick(e, emp, d)}
                        title={`${emp.name} - ${d.date}: ${entry?.status || 'No data'}`}
                        className={`border-b border-gray-100 p-0.5 text-center cursor-pointer hover:opacity-80 transition-opacity
                          ${d.isSunday || d.isSaturday ? 'bg-gray-50' : ''}`}
                      >
                        <div className={`rounded px-0.5 py-0.5 text-[10px] font-medium leading-tight
                          ${colorClass} ${hasConflict ? 'ring-2 ring-red-400 ring-inset' : ''}`}>
                          {abbr || (entry ? statusShort(entry.status) : '')}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {filteredEmployees.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              No employees match the current filters.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
