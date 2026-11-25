import { useMemo } from 'react'
import { getDateArray } from '../../utils/dateUtils'
import Badge from '../ui/Badge'

export default function ProcessWiseView({ processSummary, processes, year, month }) {
  const dateArray = useMemo(() => getDateArray(year, month), [year, month])

  // Build a map: processId -> { date -> { available, required } }
  const coverageMap = useMemo(() => {
    const map = {}
    if (Array.isArray(processSummary)) {
      processSummary.forEach(row => {
        const pid = row.process_id || row.process
        if (!map[pid]) map[pid] = {}
        if (row.date) {
          map[pid][row.date] = { available: row.available ?? row.staff_count ?? 0, required: row.required ?? row.min_required ?? 0 }
        }
      })
    }
    return map
  }, [processSummary])

  // Summary stats per process
  const processList = useMemo(() => {
    return processes.map(proc => {
      const dailyData = coverageMap[proc.id] || {}
      let metDays = 0, shortDays = 0, totalDays = 0
      dateArray.forEach(d => {
        const { available = 0, required = 0 } = dailyData[d.date] || {}
        if (required > 0) {
          totalDays++
          if (available >= required) metDays++
          else shortDays++
        }
      })
      return { proc, dailyData, metDays, shortDays, totalDays }
    })
  }, [processes, coverageMap, dateArray])

  if (processes.length === 0) {
    return <div className="text-center py-16 text-gray-400">No processes configured.</div>
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {processList.map(({ proc, metDays, shortDays, totalDays }) => (
          <div key={proc.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="font-semibold text-gray-800 mb-2 truncate">{proc.name}</div>
            <div className="flex gap-3 text-sm">
              <div>
                <div className="text-green-600 font-bold">{metDays}</div>
                <div className="text-xs text-gray-500">Days met</div>
              </div>
              <div>
                <div className="text-red-600 font-bold">{shortDays}</div>
                <div className="text-xs text-gray-500">Days short</div>
              </div>
              <div>
                <div className="text-gray-600 font-bold">{totalDays}</div>
                <div className="text-xs text-gray-500">Total req</div>
              </div>
            </div>
            {totalDays > 0 && (
              <div className="mt-2 bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${metDays / totalDays >= 0.9 ? 'bg-green-500' : metDays / totalDays >= 0.7 ? 'bg-amber-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.round((metDays / totalDays) * 100)}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Process matrix */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
          <h2 className="font-semibold text-gray-800">Daily Process Coverage</h2>
          <p className="text-xs text-gray-500 mt-0.5">Each cell shows available/required. Green = met, Red = short.</p>
        </div>
        <div className="overflow-x-auto scrollbar-thin">
          <table className="text-xs border-collapse min-w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="sticky left-0 z-10 bg-gray-50 border-b border-r border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 min-w-[160px]">Process</th>
                {dateArray.map(d => (
                  <th key={d.date} className={`border-b border-gray-200 px-0.5 py-1 text-center min-w-[36px] w-10 ${d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-400' : 'text-gray-500'}`}>
                    <div>{d.day}</div>
                    <div className="text-[9px] text-gray-400">{d.dayLabel}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {processList.map(({ proc, dailyData }, ri) => (
                <tr key={proc.id} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="sticky left-0 z-10 border-b border-r border-gray-200 px-3 py-2 bg-inherit">
                    <div className="font-medium text-gray-800">{proc.name}</div>
                    {proc.min_required != null && (
                      <div className="text-gray-400 text-[10px]">Min: {proc.min_required}</div>
                    )}
                  </td>
                  {dateArray.map(d => {
                    const { available = 0, required = 0 } = dailyData[d.date] || {}
                    const met = required > 0 && available >= required
                    const short = required > 0 && available < required
                    return (
                      <td key={d.date} className="border-b border-gray-100 p-0.5 text-center">
                        {required > 0 ? (
                          <div className={`rounded text-[10px] font-semibold py-0.5 ${met ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-700'}`}>
                            {available}/{required}
                          </div>
                        ) : (
                          <div className="rounded text-[10px] py-0.5 text-gray-300">—</div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
