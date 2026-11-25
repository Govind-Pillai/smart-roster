import { useState, useMemo } from 'react'
import { X, AlertTriangle, CheckCircle, ChevronRight } from 'lucide-react'
import Badge from '../ui/Badge'
import Button from '../ui/Button'

const FILTER_TABS = ['All', 'Critical', 'Warning', 'Resolved']

export default function ConflictsPanel({ conflicts, onResolve, onClose }) {
  const [activeFilter, setActiveFilter] = useState('All')
  const [resolvingId, setResolvingId] = useState(null)

  const filtered = useMemo(() => {
    switch (activeFilter) {
      case 'Critical': return conflicts.filter(c => c.severity === 'CRITICAL' && !c.resolved)
      case 'Warning': return conflicts.filter(c => c.severity === 'WARNING' && !c.resolved)
      case 'Resolved': return conflicts.filter(c => c.resolved)
      default: return conflicts
    }
  }, [conflicts, activeFilter])

  const criticalCount = conflicts.filter(c => c.severity === 'CRITICAL' && !c.resolved).length
  const warningCount = conflicts.filter(c => c.severity === 'WARNING' && !c.resolved).length
  const resolvedCount = conflicts.filter(c => c.resolved).length

  const handleResolve = async (id) => {
    setResolvingId(id)
    try { await onResolve(id) } finally { setResolvingId(null) }
  }

  const getTabCount = (tab) => {
    switch (tab) {
      case 'Critical': return criticalCount
      case 'Warning': return warningCount
      case 'Resolved': return resolvedCount
      default: return conflicts.length
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <h3 className="font-semibold text-gray-800 text-sm">Conflicts & Resolutions</h3>
          <div className="flex items-center gap-2 mt-0.5">
            {criticalCount > 0 && (
              <span className="text-xs text-red-600 font-medium">{criticalCount} critical</span>
            )}
            {warningCount > 0 && (
              <span className="text-xs text-amber-500 font-medium">{warningCount} warnings</span>
            )}
            {criticalCount === 0 && warningCount === 0 && (
              <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                <CheckCircle size={12} /> All clear
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-200 text-gray-500 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex border-b border-gray-200 bg-white">
        {FILTER_TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveFilter(tab)}
            className={`flex-1 py-2 text-xs font-medium transition-colors border-b-2
              ${activeFilter === tab
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            {tab}
            <span className={`ml-1 px-1 py-0.5 rounded text-[10px] font-semibold
              ${tab === 'Critical' ? 'bg-red-100 text-red-700' : tab === 'Warning' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>
              {getTabCount(tab)}
            </span>
          </button>
        ))}
      </div>

      {/* Conflict list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <CheckCircle size={32} className="mb-2 text-green-400" />
            <p className="text-sm font-medium">No conflicts here</p>
            <p className="text-xs mt-1">
              {activeFilter === 'All' ? 'Generate a roster to check conflicts' : `No ${activeFilter.toLowerCase()} conflicts`}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map(conflict => (
              <div
                key={conflict.id}
                className={`p-3 hover:bg-gray-50 transition-colors ${conflict.resolved ? 'opacity-60' : ''}`}
              >
                {/* Badges row */}
                <div className="flex items-center gap-1.5 mb-2 flex-wrap">
                  <Badge variant={conflict.severity === 'CRITICAL' ? 'danger' : 'warning'}>
                    <AlertTriangle size={10} className="mr-0.5" />
                    {conflict.severity}
                  </Badge>
                  {conflict.conflict_type && (
                    <Badge variant="default" className="text-[10px]">
                      {conflict.conflict_type.replace(/_/g, ' ')}
                    </Badge>
                  )}
                  {conflict.resolved && (
                    <Badge variant="success">Resolved</Badge>
                  )}
                </div>

                {/* Date and entities */}
                <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
                  {conflict.date && <span className="font-mono bg-gray-100 px-1 rounded">{conflict.date}</span>}
                  {conflict.brand_name && <span className="text-blue-600">{conflict.brand_name}</span>}
                  {conflict.employee_name && (
                    <>
                      <ChevronRight size={10} />
                      <span>{conflict.employee_name}</span>
                    </>
                  )}
                </div>

                {/* Description */}
                <p className="text-xs text-gray-700 leading-relaxed mb-2">
                  {conflict.description || conflict.message || `${conflict.conflict_type} conflict detected`}
                </p>

                {/* Suggested resolution */}
                {conflict.suggested_resolution && (
                  <p className="text-xs text-gray-500 italic mb-2">
                    💡 {conflict.suggested_resolution}
                  </p>
                )}

                {/* Backup employee */}
                {conflict.backup_employee_name && (
                  <p className="text-xs text-teal-600 mb-2">
                    Backup: {conflict.backup_employee_name}
                  </p>
                )}

                {/* Action button */}
                {!conflict.resolved && (
                  <Button
                    size="xs"
                    variant={conflict.severity === 'CRITICAL' ? 'danger' : 'warning'}
                    loading={resolvingId === conflict.id}
                    onClick={() => handleResolve(conflict.id)}
                    className="w-full mt-1"
                  >
                    {conflict.backup_employee_name ? 'Apply Backup & Resolve' : 'Mark Resolved'}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
