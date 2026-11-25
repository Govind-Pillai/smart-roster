import { useState } from 'react'
import { rosterApi } from '../../api/client'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Select from '../ui/Select'

const LEAVE_TYPES = [
  { value: 'PLANNED_LEAVE', label: 'Planned Leave' },
  { value: 'COMP_OFF', label: 'Comp Off' },
  { value: 'UNAVAILABLE', label: 'Unavailable' },
]

const STATUS_OPTIONS = [
  { value: 'APPROVED', label: 'Approved' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'REJECTED', label: 'Rejected' },
]

function getTodayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function AddLeaveModal({ employees, onClose, onSave }) {
  const [form, setForm] = useState({
    employee: '',
    leave_type: 'PLANNED_LEAVE',
    start_date: getTodayStr(),
    end_date: getTodayStr(),
    notes: '',
    status: 'APPROVED',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const empOptions = [
    { value: '', label: 'Select employee…' },
    ...employees.map(e => ({ value: String(e.id), label: e.name })),
  ]

  const set = (field) => (value) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setError('')
  }

  const validate = () => {
    if (!form.employee) return 'Please select an employee.'
    if (!form.start_date) return 'Start date is required.'
    if (!form.end_date) return 'End date is required.'
    if (form.end_date < form.start_date) return 'End date must be on or after start date.'
    return ''
  }

  const handleSave = async () => {
    const err = validate()
    if (err) { setError(err); return }
    setSaving(true)
    try {
      await rosterApi.createLeave({
        employee: Number(form.employee),
        leave_type: form.leave_type,
        start_date: form.start_date,
        end_date: form.end_date,
        notes: form.notes,
        status: form.status,
      })
      onSave()
    } catch (e) {
      setError(e.response?.data?.detail || JSON.stringify(e.response?.data) || 'Failed to save leave request.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Add Leave Request"
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>Save Leave</Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">{error}</div>
        )}

        {/* Employee */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Employee <span className="text-red-500">*</span></label>
          <Select
            value={form.employee}
            onChange={set('employee')}
            options={empOptions}
            className="w-full"
          />
        </div>

        {/* Leave type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Leave Type</label>
          <Select
            value={form.leave_type}
            onChange={set('leave_type')}
            options={LEAVE_TYPES}
            className="w-full"
          />
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              value={form.start_date}
              onChange={e => set('start_date')(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              value={form.end_date}
              min={form.start_date}
              onChange={e => set('end_date')(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Status */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
          <Select
            value={form.status}
            onChange={set('status')}
            options={STATUS_OPTIONS}
            className="w-full"
          />
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <textarea
            value={form.notes}
            onChange={e => set('notes')(e.target.value)}
            rows={3}
            placeholder="Optional notes or reason for leave…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}
