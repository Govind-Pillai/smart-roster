import { useState, useEffect } from 'react'
import { rosterApi } from '../../api/client'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Select from '../ui/Select'
import { Plus, Trash2, CheckCircle, Settings, Users, Building, Sliders, UserCheck } from 'lucide-react'

const DAYS_OF_WEEK = [
  { value: '0', label: 'Monday' },
  { value: '1', label: 'Tuesday' },
  { value: '2', label: 'Wednesday' },
  { value: '3', label: 'Thursday' },
  { value: '4', label: 'Friday' },
  { value: '5', label: 'Saturday' },
  { value: '6', label: 'Sunday' },
]

const OPERATING_RULES = [
  { value: '365_DAYS', label: '365 Days (No Offs/Holidays for process)' },
  { value: 'EXCEPT_HOLIDAYS', label: 'Except Holidays (Mon-Sun minus Holidays)' },
  { value: 'NO_SUNDAYS_OR_HOLIDAYS', label: 'No Sundays or Holidays' },
]

const ROLE_TYPES = [
  { value: 'PRIMARY', label: 'Primary' },
  { value: 'SHARED', label: 'Shared' },
  { value: 'BACKUP', label: 'Backup' },
]

export default function ConfigModal({ pods, brands, processes, employees, onClose, onRefreshData }) {
  const [activeSubTab, setActiveSubTab] = useState('employees')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState(null)

  // Data lists
  const [configsList, setConfigsList] = useState([])
  const [allocationsList, setAllocationsList] = useState([])

  // Employee Form state
  const [empName, setEmpName] = useState('')
  const [empEmail, setEmpEmail] = useState('')
  const [empPod, setEmpPod] = useState(pods[0]?.id ? String(pods[0].id) : '')
  const [empIsLead, setEmpIsLead] = useState(false)
  const [empPrefOff, setEmpPrefOff] = useState('6')

  // Brand Form state
  const [brandName, setBrandName] = useState('')
  const [brandPod, setBrandPod] = useState(pods[0]?.id ? String(pods[0].id) : '')

  // Config Form state
  const [cfgBrand, setCfgBrand] = useState(brands[0]?.id ? String(brands[0].id) : '')
  const [cfgProcess, setCfgProcess] = useState(processes[0]?.id ? String(processes[0].id) : '')
  const [cfgRule, setCfgRule] = useState('EXCEPT_HOLIDAYS')
  const [cfgMinStaff, setCfgMinStaff] = useState('1')

  // Allocation Form state
  const [allocEmp, setAllocEmp] = useState(employees[0]?.id ? String(employees[0].id) : '')
  const [allocBrand, setAllocBrand] = useState(brands[0]?.id ? String(brands[0].id) : '')
  const [allocProcess, setAllocProcess] = useState(processes[0]?.id ? String(processes[0].id) : '')
  const [allocRole, setAllocRole] = useState('PRIMARY')

  const fetchConfigsAndAllocs = async () => {
    try {
      const [cRes, aRes] = await Promise.all([
        rosterApi.getConfigs(),
        rosterApi.getAllocations(),
      ])
      setConfigsList(cRes.data.results || cRes.data || [])
      setAllocationsList(aRes.data.results || aRes.data || [])
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchConfigsAndAllocs()
  }, [])

  const notify = (text, type = 'success') => {
    setMsg({ text, type })
    setTimeout(() => setMsg(null), 3500)
  }

  // Submit Handlers
  const handleAddEmployee = async (e) => {
    e.preventDefault()
    if (!empName || !empEmail || !empPod) return
    setLoading(true)
    try {
      await rosterApi.createEmployee({
        name: empName,
        email: empEmail,
        pod: parseInt(empPod),
        is_pod_lead: empIsLead,
        preferred_weekly_off: parseInt(empPrefOff),
        max_working_days_per_week: 6,
      })
      notify(`Employee "${empName}" added!`)
      setEmpName('')
      setEmpEmail('')
      if (onRefreshData) onRefreshData()
    } catch (err) {
      notify('Error adding employee: ' + (err.response?.data?.error || JSON.stringify(err.response?.data) || err.message), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAddBrand = async (e) => {
    e.preventDefault()
    if (!brandName || !brandPod) return
    setLoading(true)
    try {
      await rosterApi.createBrand({
        name: brandName,
        pod: parseInt(brandPod),
        is_active: true,
      })
      notify(`Brand "${brandName}" created!`)
      setBrandName('')
      if (onRefreshData) onRefreshData()
    } catch (err) {
      notify('Error adding brand: ' + (err.response?.data?.error || err.message), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAddConfig = async (e) => {
    e.preventDefault()
    if (!cfgBrand || !cfgProcess) return
    setLoading(true)
    try {
      await rosterApi.createConfig({
        brand: parseInt(cfgBrand),
        process: parseInt(cfgProcess),
        operating_rule: cfgRule,
        min_daily_staff: parseInt(cfgMinStaff) || 1,
        day_of_week_overrides: {},
      })
      notify('Brand Process Rule saved!')
      fetchConfigsAndAllocs()
      if (onRefreshData) onRefreshData()
    } catch (err) {
      notify('Error saving config: ' + (err.response?.data?.error || JSON.stringify(err.response?.data) || err.message), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAddAllocation = async (e) => {
    e.preventDefault()
    if (!allocEmp || !allocBrand || !allocProcess) return
    setLoading(true)
    try {
      await rosterApi.createAllocation({
        employee: parseInt(allocEmp),
        brand: parseInt(allocBrand),
        process: parseInt(allocProcess),
        role_type: allocRole,
      })
      notify('Resource allocation assigned!')
      fetchConfigsAndAllocs()
      if (onRefreshData) onRefreshData()
    } catch (err) {
      notify('Error assigning allocation: ' + (err.response?.data?.error || JSON.stringify(err.response?.data) || err.message), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAllocation = async (id) => {
    try {
      await rosterApi.deleteAllocation(id)
      notify('Allocation removed')
      fetchConfigsAndAllocs()
      if (onRefreshData) onRefreshData()
    } catch (err) {
      notify('Failed to delete allocation', 'error')
    }
  }

  return (
    <Modal
      title="System Configuration & Operations Management"
      onClose={onClose}
      size="xl"
      footer={<Button variant="secondary" onClick={onClose}>Close</Button>}
    >
      {msg && (
        <div className={`p-3 mb-4 rounded-lg text-sm font-medium flex items-center gap-2 ${
          msg.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'
        }`}>
          <CheckCircle size={16} />
          {msg.text}
        </div>
      )}

      {/* Sub Tabs */}
      <div className="flex border-b border-gray-200 mb-5 gap-2 text-sm font-medium">
        <button
          onClick={() => setActiveSubTab('employees')}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 transition-colors ${
            activeSubTab === 'employees' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Users size={16} /> Employees ({employees.length})
        </button>
        <button
          onClick={() => setActiveSubTab('brands')}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 transition-colors ${
            activeSubTab === 'brands' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Building size={16} /> Brands ({brands.length})
        </button>
        <button
          onClick={() => setActiveSubTab('configs')}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 transition-colors ${
            activeSubTab === 'configs' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Sliders size={16} /> Process Rules ({configsList.length})
        </button>
        <button
          onClick={() => setActiveSubTab('allocations')}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 transition-colors ${
            activeSubTab === 'allocations' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <UserCheck size={16} /> Allocations ({allocationsList.length})
        </button>
      </div>

      {/* Tab 1: Employees */}
      {activeSubTab === 'employees' && (
        <div className="space-y-6">
          <form onSubmit={handleAddEmployee} className="bg-gray-50 p-4 rounded-xl border border-gray-200 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Full Name</label>
              <input
                type="text"
                required
                value={empName}
                onChange={e => setEmpName(e.target.value)}
                placeholder="e.g. Maya Patel"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Email</label>
              <input
                type="email"
                required
                value={empEmail}
                onChange={e => setEmpEmail(e.target.value)}
                placeholder="e.g. maya@company.com"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Operational Pod</label>
              <Select
                value={empPod}
                onChange={setEmpPod}
                options={pods.map(p => ({ value: String(p.id), label: p.name }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Preferred Weekly Off</label>
              <Select
                value={empPrefOff}
                onChange={setEmpPrefOff}
                options={DAYS_OF_WEEK}
              />
            </div>
            <div className="flex items-center gap-2 pt-5">
              <input
                type="checkbox"
                id="isLeadCheck"
                checked={empIsLead}
                onChange={e => setEmpIsLead(e.target.checked)}
                className="rounded text-blue-600"
              />
              <label htmlFor="isLeadCheck" className="text-xs font-medium text-gray-700">Designate as Pod Lead</label>
            </div>
            <div className="flex items-end">
              <Button type="submit" variant="primary" loading={loading} className="w-full">
                <Plus size={14} /> Add Employee
              </Button>
            </div>
          </form>

          <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-100 text-gray-600 sticky top-0">
                <tr>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Pod</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-3 py-2">Pref Off</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {employees.map(e => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-3 py-1.5 font-medium text-gray-900">{e.name}</td>
                    <td className="px-3 py-1.5 text-gray-500">{e.email}</td>
                    <td className="px-3 py-1.5">{e.pod_name || pods.find(p => p.id === e.pod)?.name || e.pod}</td>
                    <td className="px-3 py-1.5">{e.is_pod_lead ? <span className="text-blue-600 font-semibold">Pod Lead</span> : 'Member'}</td>
                    <td className="px-3 py-1.5">{DAYS_OF_WEEK.find(d => d.value === String(e.preferred_weekly_off))?.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Brands */}
      {activeSubTab === 'brands' && (
        <div className="space-y-6">
          <form onSubmit={handleAddBrand} className="bg-gray-50 p-4 rounded-xl border border-gray-200 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Brand Name</label>
              <input
                type="text"
                required
                value={brandName}
                onChange={e => setBrandName(e.target.value)}
                placeholder="e.g. Apex Audio"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Managing Pod</label>
              <Select
                value={brandPod}
                onChange={setBrandPod}
                options={pods.map(p => ({ value: String(p.id), label: p.name }))}
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" variant="primary" loading={loading} className="w-full">
                <Plus size={14} /> Create Brand
              </Button>
            </div>
          </form>

          <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-100 text-gray-600 sticky top-0">
                <tr>
                  <th className="px-3 py-2">Brand Name</th>
                  <th className="px-3 py-2">Pod</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {brands.map(b => (
                  <tr key={b.id} className="hover:bg-gray-50">
                    <td className="px-3 py-1.5 font-medium text-gray-900">{b.name}</td>
                    <td className="px-3 py-1.5">{b.pod_name || pods.find(p => p.id === b.pod)?.name || b.pod}</td>
                    <td className="px-3 py-1.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-green-100 text-green-700">Active</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Process Rules */}
      {activeSubTab === 'configs' && (
        <div className="space-y-6">
          <form onSubmit={handleAddConfig} className="bg-gray-50 p-4 rounded-xl border border-gray-200 grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Brand</label>
              <Select
                value={cfgBrand}
                onChange={setCfgBrand}
                options={brands.map(b => ({ value: String(b.id), label: b.name }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Process</label>
              <Select
                value={cfgProcess}
                onChange={setCfgProcess}
                options={processes.map(p => ({ value: String(p.id), label: p.name }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Operating Rule</label>
              <Select
                value={cfgRule}
                onChange={setCfgRule}
                options={OPERATING_RULES}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Min Daily Staff</label>
              <input
                type="number"
                min="1"
                max="10"
                value={cfgMinStaff}
                onChange={e => setCfgMinStaff(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-blue-500"
              />
            </div>
            <div className="md:col-span-4 flex justify-end">
              <Button type="submit" variant="primary" loading={loading}>
                <Plus size={14} /> Add / Update Process Rule
              </Button>
            </div>
          </form>

          <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-100 text-gray-600 sticky top-0">
                <tr>
                  <th className="px-3 py-2">Brand</th>
                  <th className="px-3 py-2">Process</th>
                  <th className="px-3 py-2">Rule</th>
                  <th className="px-3 py-2">Min Staff</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {configsList.map(c => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-3 py-1.5 font-medium">{c.brand_name || brands.find(b => b.id === c.brand)?.name || c.brand}</td>
                    <td className="px-3 py-1.5">{c.process_name || processes.find(p => p.id === c.process)?.name || c.process}</td>
                    <td className="px-3 py-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        c.operating_rule === '365_DAYS' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                        {c.operating_rule}
                      </span>
                    </td>
                    <td className="px-3 py-1.5">{c.min_daily_staff}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Allocations */}
      {activeSubTab === 'allocations' && (
        <div className="space-y-6">
          <form onSubmit={handleAddAllocation} className="bg-gray-50 p-4 rounded-xl border border-gray-200 grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Employee</label>
              <Select
                value={allocEmp}
                onChange={setAllocEmp}
                options={employees.map(e => ({ value: String(e.id), label: `${e.name} (${e.pod_name || 'Pod'})` }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Brand</label>
              <Select
                value={allocBrand}
                onChange={setAllocBrand}
                options={brands.map(b => ({ value: String(b.id), label: b.name }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Process</label>
              <Select
                value={allocProcess}
                onChange={setAllocProcess}
                options={processes.map(p => ({ value: String(p.id), label: p.name }))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Role Type</label>
              <Select
                value={allocRole}
                onChange={setAllocRole}
                options={ROLE_TYPES}
              />
            </div>
            <div className="md:col-span-4 flex justify-end">
              <Button type="submit" variant="primary" loading={loading}>
                <Plus size={14} /> Assign Allocation
              </Button>
            </div>
          </form>

          <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-100 text-gray-600 sticky top-0">
                <tr>
                  <th className="px-3 py-2">Employee</th>
                  <th className="px-3 py-2">Brand</th>
                  <th className="px-3 py-2">Process</th>
                  <th className="px-3 py-2">Role Type</th>
                  <th className="px-3 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {allocationsList.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-3 py-1.5 font-medium">{a.employee_name || employees.find(e => e.id === a.employee)?.name || a.employee}</td>
                    <td className="px-3 py-1.5">{a.brand_name || brands.find(b => b.id === a.brand)?.name || a.brand}</td>
                    <td className="px-3 py-1.5">{a.process_name || processes.find(p => p.id === a.process)?.name || a.process}</td>
                    <td className="px-3 py-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        a.role_type === 'PRIMARY' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                      }`}>
                        {a.role_type}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        onClick={() => handleDeleteAllocation(a.id)}
                        className="text-red-500 hover:text-red-700 p-1"
                        title="Delete allocation"
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  )
}
