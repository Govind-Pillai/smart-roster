import { Calendar, RefreshCw, AlertTriangle, Plus, Filter, Settings } from 'lucide-react'
import { MONTHS } from '../../utils/dateUtils'
import Button from '../ui/Button'
import Select from '../ui/Select'

const currentYear = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: 5 }, (_, i) => ({
  value: currentYear - 2 + i,
  label: String(currentYear - 2 + i),
}))
const MONTH_OPTIONS = MONTHS.map((m, i) => ({ value: i + 1, label: m }))

export default function TopControlBar({
  year, month,
  onYearChange, onMonthChange,
  onGenerate, generating,
  criticalCount, warningCount,
  onShowConflicts, onAddLeave, onOpenConfig,
  filterPod, setFilterPod, pods,
  filterConflictsOnly, setFilterConflictsOnly,
}) {
  const podOptions = [
    { value: 'all', label: 'All Pods' },
    ...(pods || []).map(p => ({ value: String(p.id), label: p.name })),
  ]

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex flex-wrap items-center gap-3">
      {/* Brand */}
      <div className="flex items-center gap-2 mr-2">
        <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
          <Calendar size={16} className="text-white" />
        </div>
        <span className="font-bold text-gray-900 text-sm hidden sm:block">Smart Roster</span>
      </div>

      {/* Month / Year pickers */}
      <div className="flex items-center gap-2">
        <Select
          value={month}
          onChange={v => onMonthChange(Number(v))}
          options={MONTH_OPTIONS}
          className="w-36"
        />
        <Select
          value={year}
          onChange={v => onYearChange(Number(v))}
          options={YEAR_OPTIONS}
          className="w-24"
        />
      </div>

      {/* Generate Roster */}
      <Button
        onClick={onGenerate}
        loading={generating}
        disabled={generating}
        variant="primary"
        size="sm"
      >
        <RefreshCw size={14} />
        {generating ? 'Generating…' : 'Generate Roster'}
      </Button>

      {/* Conflict badge */}
      <button
        onClick={onShowConflicts}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors hover:bg-gray-50 text-sm font-medium"
        title="Toggle conflicts panel"
      >
        <AlertTriangle size={14} className={criticalCount > 0 ? 'text-red-500' : 'text-amber-400'} />
        {criticalCount > 0 && (
          <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-xs font-semibold">
            {criticalCount} Critical
          </span>
        )}
        {warningCount > 0 && (
          <span className="bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded text-xs font-semibold">
            {warningCount} Warn
          </span>
        )}
        {criticalCount === 0 && warningCount === 0 && (
          <span className="text-green-600 text-xs">No conflicts</span>
        )}
      </button>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Pod filter */}
      <div className="flex items-center gap-1.5">
        <Filter size={14} className="text-gray-400" />
        <Select
          value={filterPod}
          onChange={setFilterPod}
          options={podOptions}
          className="w-36"
        />
      </div>

      {/* Conflicts only checkbox */}
      <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={filterConflictsOnly}
          onChange={e => setFilterConflictsOnly(e.target.checked)}
          className="rounded border-gray-300 text-blue-600"
        />
        Conflicts only
      </label>

      {/* Add Leave */}
      <Button onClick={onAddLeave} variant="secondary" size="sm">
        <Plus size={14} />
        Add Leave
      </Button>

      {/* Config / Admin */}
      <Button onClick={onOpenConfig} variant="secondary" size="sm" title="Configure Employees, Brands & Rules">
        <Settings size={14} />
        Config
      </Button>
    </header>
  )
}
