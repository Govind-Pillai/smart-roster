import { useState, useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import Button from '../ui/Button'
import Select from '../ui/Select'

const STATUS_OPTIONS = [
  { value: 'WORKING', label: 'Working' },
  { value: 'WEEKLY_OFF', label: 'Weekly Off' },
  { value: 'PUBLIC_HOLIDAY', label: 'Public Holiday' },
  { value: 'PLANNED_LEAVE', label: 'Planned Leave' },
  { value: 'COMP_OFF', label: 'Comp Off' },
]

const STATUS_COLORS = {
  WORKING: 'bg-blue-100 text-blue-800',
  WEEKLY_OFF: 'bg-gray-100 text-gray-700',
  PUBLIC_HOLIDAY: 'bg-purple-100 text-purple-800',
  PLANNED_LEAVE: 'bg-amber-100 text-amber-800',
  COMP_OFF: 'bg-teal-100 text-teal-800',
}

export default function CellEditPopover({ entryId, date, status: initStatus, brandId: initBrandId, processId: initProcessId, brands, processes, onSave, onClose }) {
  const [status, setStatus] = useState(initStatus || 'WORKING')
  const [brandId, setBrandId] = useState(String(initBrandId || ''))
  const [processId, setProcessId] = useState(String(initProcessId || ''))
  const ref = useRef(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const brandOptions = [
    { value: '', label: 'No brand' },
    ...brands.map(b => ({ value: String(b.id), label: b.name })),
  ]
  const processOptions = [
    { value: '', label: 'No process' },
    ...processes.map(p => ({ value: String(p.id), label: p.name })),
  ]

  const handleSave = () => {
    onSave({
      status,
      brand: brandId ? Number(brandId) : null,
      process: processId ? Number(processId) : null,
    })
  }

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center pt-24 px-4" onClick={onClose}>
      <div
        ref={ref}
        className="bg-white rounded-xl shadow-2xl border border-gray-200 w-72 p-4"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="font-semibold text-gray-800 text-sm">Edit Roster Cell</h4>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{date}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 text-gray-400"><X size={14} /></button>
        </div>

        {/* Status radio */}
        <div className="mb-3">
          <label className="block text-xs font-medium text-gray-600 mb-1.5">Status</label>
          <div className="grid grid-cols-1 gap-1">
            {STATUS_OPTIONS.map(opt => (
              <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="status"
                  value={opt.value}
                  checked={status === opt.value}
                  onChange={() => setStatus(opt.value)}
                  className="text-blue-600"
                />
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLORS[opt.value]}`}>
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Brand & Process (only when WORKING) */}
        {status === 'WORKING' && (
          <div className="space-y-2 mb-3 pt-2 border-t border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Brand</label>
              <Select value={brandId} onChange={setBrandId} options={brandOptions} className="w-full text-xs" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Process</label>
              <Select value={processId} onChange={setProcessId} options={processOptions} className="w-full text-xs" />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2 border-t border-gray-100">
          <Button size="xs" variant="secondary" onClick={onClose} className="flex-1">Cancel</Button>
          <Button size="xs" variant="primary" onClick={handleSave} className="flex-1">Save</Button>
        </div>
      </div>
    </div>
  )
}
