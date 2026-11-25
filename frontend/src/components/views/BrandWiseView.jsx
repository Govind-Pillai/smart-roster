import { useMemo, useState } from 'react'
import { getDateArray } from '../../utils/dateUtils'
import Badge from '../ui/Badge'
import Select from '../ui/Select'

export default function BrandWiseView({
  brandSummary, brands, rosterData, year, month, conflicts, employees,
}) {
  const [filterPod, setFilterPod] = useState('all')
  const dateArray = useMemo(() => getDateArray(year, month), [year, month])

  // Extract unique pods from brands
  const podOptions = useMemo(() => {
    const pods = {}
    brands.forEach(b => { if (b.pod_name || b.pod) pods[b.pod || b.pod_name] = b.pod_name || b.pod })
    return [
      { value: 'all', label: 'All Pods' },
      ...Object.entries(pods).map(([v, l]) => ({ value: v, label: l })),
    ]
  }, [brands])

  // Merge brands with their summary data
  const brandRows = useMemo(() => {
    return brands
      .filter(b => filterPod === 'all' || String(b.pod || b.pod_name) === filterPod)
      .map(brand => {
        const summary = brandSummary.find(s => s.brand_id === brand.id || s.brand === brand.id) || {}
        return { brand, summary }
      })
  }, [brands, brandSummary, filterPod])

  // Build daily coverage from rosterData
  const getDailyCoverage = (brandId, date) => {
    const entries = rosterData.filter(e =>
      (e.brand_id === brandId || e.brand === brandId) &&
      e.date === date &&
      e.status === 'WORKING'
    )
    return entries.length
  }

  const getCoverageClass = (count, minStaff) => {
    if (!minStaff) return 'bg-gray-100'
    if (count === 0) return 'bg-gray-100 text-gray-400'
    if (count >= minStaff) return 'bg-green-100 text-green-800'
    return 'bg-red-100 text-red-700'
  }

  if (brands.length === 0) {
    return <div className="text-center py-16 text-gray-400">No brands configured.</div>
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">Brand-Wise Coverage</h2>
          <Select value={filterPod} onChange={setFilterPod} options={podOptions} className="w-40" />
        </div>

        <div className="overflow-x-auto scrollbar-thin">
          <table className="text-xs border-collapse min-w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="sticky left-0 z-10 bg-gray-50 border-b border-r border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 min-w-[160px]">Brand</th>
                <th className="border-b border-gray-200 px-3 py-2 text-left font-medium text-gray-600 min-w-[90px]">Rule</th>
                <th className="border-b border-gray-200 px-3 py-2 text-center font-medium text-gray-600 min-w-[80px]">Assigned</th>
                {dateArray.map(d => (
                  <th key={d.date} className={`border-b border-gray-200 px-0.5 py-1 text-center min-w-[30px] w-8 ${d.isSunday || d.isSaturday ? 'bg-gray-100 text-gray-400' : 'text-gray-500'}`}>
                    <div>{d.day}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brandRows.map(({ brand, summary }, ri) => (
                <tr key={brand.id} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="sticky left-0 z-10 border-b border-r border-gray-200 px-3 py-2 bg-inherit">
                    <div className="font-medium text-gray-800">{brand.name}</div>
                    <div className="text-gray-400 text-[10px]">{brand.pod_name || ''}</div>
                  </td>
                  <td className="border-b border-gray-200 px-3 py-2">
                    <Badge variant={brand.min_staff ? 'primary' : 'default'}>
                      Min {brand.min_staff || summary.min_staff || '?'}
                    </Badge>
                  </td>
                  <td className="border-b border-gray-200 px-3 py-2 text-center">
                    <span className="font-semibold text-gray-700">
                      {summary.total_assigned || rosterData.filter(e => (e.brand_id === brand.id || e.brand === brand.id) && e.status === 'WORKING').length}
                    </span>
                  </td>
                  {dateArray.map(d => {
                    const count = getDailyCoverage(brand.id, d.date)
                    const minStaff = brand.min_staff || summary.min_staff || 0
                    const cls = getCoverageClass(count, minStaff)
                    return (
                      <td key={d.date} className="border-b border-gray-100 p-0.5 text-center">
                        <div className={`rounded text-[10px] font-medium py-0.5 ${cls}`} title={`${brand.name} on ${d.date}: ${count} working`}>
                          {count > 0 ? count : ''}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-100 inline-block" /> Met minimum</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-100 inline-block" /> Understaffed</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-gray-100 inline-block" /> No requirement / empty</span>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {brandRows.slice(0, 8).map(({ brand, summary }) => {
          const workingDays = rosterData.filter(e => (e.brand_id === brand.id || e.brand === brand.id) && e.status === 'WORKING').length
          const coverageRate = summary.coverage_rate ?? (workingDays > 0 ? Math.min(100, Math.round(workingDays / Math.max(1, (brand.min_staff || 1) * dateArray.length) * 100)) : 0)
          return (
            <div key={brand.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <div className="font-semibold text-gray-800 mb-1 truncate">{brand.name}</div>
              <div className="text-2xl font-bold text-blue-600 mb-1">{coverageRate}%</div>
              <div className="text-xs text-gray-500">Coverage rate</div>
              <div className="mt-2 bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${coverageRate >= 90 ? 'bg-green-500' : coverageRate >= 70 ? 'bg-amber-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.min(100, coverageRate)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
