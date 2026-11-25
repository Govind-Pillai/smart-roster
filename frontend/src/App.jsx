import { useState, useEffect, useCallback } from 'react'
import { rosterApi } from './api/client'
import TopControlBar from './components/layout/TopControlBar'
import CompanyWideView from './components/views/CompanyWideView'
import PodWiseView from './components/views/PodWiseView'
import BrandWiseView from './components/views/BrandWiseView'
import ProcessWiseView from './components/views/ProcessWiseView'
import EmployeeWiseView from './components/views/EmployeeWiseView'
import ConflictsPanel from './components/panels/ConflictsPanel'
import AddLeaveModal from './components/modals/AddLeaveModal'
import ConfigModal from './components/modals/ConfigModal'
import { X } from 'lucide-react'

const TABS = [
  { id: 'company', label: 'Company-Wide' },
  { id: 'pod', label: 'Pod-Wise' },
  { id: 'brand', label: 'Brand-Wise' },
  { id: 'process', label: 'Process-Wise' },
  { id: 'employee', label: 'Employee-Wise' },
]

export default function App() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [activeTab, setActiveTab] = useState('company')
  const [rosterData, setRosterData] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [brandSummary, setBrandSummary] = useState([])
  const [processSummary, setProcessSummary] = useState([])
  const [employees, setEmployees] = useState([])
  const [pods, setPods] = useState([])
  const [brands, setBrands] = useState([])
  const [processes, setProcesses] = useState([])
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showConflicts, setShowConflicts] = useState(true)
  const [showLeaveModal, setShowLeaveModal] = useState(false)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [toast, setToast] = useState(null)
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [filterPod, setFilterPod] = useState('all')
  const [filterConflictsOnly, setFilterConflictsOnly] = useState(false)

  const monthStr = `${year}-${String(month).padStart(2, '0')}`

  const showToast = (msg, type = 'info') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchStaticData = useCallback(async () => {
    try {
      const [empsRes, podsRes, brandsRes, procsRes] = await Promise.all([
        rosterApi.getEmployees(),
        rosterApi.getPods(),
        rosterApi.getBrands(),
        rosterApi.getProcesses(),
      ])
      setEmployees(empsRes.data.results || empsRes.data)
      setPods(podsRes.data.results || podsRes.data)
      setBrands(brandsRes.data.results || brandsRes.data)
      setProcesses(procsRes.data.results || procsRes.data)
    } catch (e) {
      showToast('Failed to load base data. Is the backend running?', 'error')
    }
  }, [])

  const fetchRosterData = useCallback(async () => {
    setLoading(true)
    try {
      const [rosterRes, conflictsRes, brandRes, processRes] = await Promise.all([
        rosterApi.getMonthly(year, month),
        rosterApi.getConflicts(monthStr),
        rosterApi.getBrandSummary(year, month),
        rosterApi.getProcessSummary(year, month),
      ])
      setRosterData(rosterRes.data.results || rosterRes.data || [])
      setConflicts(conflictsRes.data.results || conflictsRes.data || [])
      setBrandSummary(brandRes.data?.brands || brandRes.data?.results || brandRes.data || [])
      setProcessSummary(processRes.data?.processes || processRes.data?.results || processRes.data || [])
    } catch (e) {
      setRosterData([])
      setConflicts([])
    } finally {
      setLoading(false)
    }
  }, [year, month, monthStr])

  useEffect(() => { fetchStaticData() }, [fetchStaticData])
  useEffect(() => { fetchRosterData() }, [fetchRosterData])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await rosterApi.generate(year, month)
      showToast(
        `Roster generated! ${res.data.conflicts?.critical ?? 0} critical, ${res.data.conflicts?.warning ?? 0} warnings`,
        (res.data.conflicts?.critical ?? 0) > 0 ? 'warning' : 'success'
      )
      await fetchRosterData()
      setShowConflicts(true)
    } catch (e) {
      showToast('Generation failed: ' + (e.response?.data?.error || e.message), 'error')
    } finally {
      setGenerating(false)
    }
  }

  const handleLeaveAdded = async () => {
    setShowLeaveModal(false)
    showToast('Leave added. Re-validating roster...', 'info')
    try { await rosterApi.validate(year, month) } catch {}
    await fetchRosterData()
  }

  const handleResolveConflict = async (conflictId) => {
    try {
      await rosterApi.resolveConflict(conflictId)
      showToast('Conflict marked as resolved', 'success')
      await fetchRosterData()
    } catch (e) {
      showToast('Failed to resolve conflict', 'error')
    }
  }

  const handleCellEdit = async (entryId, updates) => {
    try {
      await rosterApi.updateEntry(entryId, { ...updates, is_manual_override: true })
      showToast('Entry updated. Re-validating...', 'info')
      try { await rosterApi.validate(year, month) } catch {}
      await fetchRosterData()
    } catch (e) {
      showToast('Update failed: ' + (e.response?.data?.error || e.message), 'error')
    }
  }

  const criticalCount = conflicts.filter(c => c.severity === 'CRITICAL' && !c.resolved).length
  const warningCount = conflicts.filter(c => c.severity === 'WARNING' && !c.resolved).length

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Toast notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-sm font-medium transition-all
          ${toast.type === 'error' ? 'bg-red-600' : toast.type === 'warning' ? 'bg-amber-500' : toast.type === 'success' ? 'bg-green-600' : 'bg-blue-600'}`}>
          {toast.msg}
          <button onClick={() => setToast(null)} className="ml-1 hover:opacity-75"><X size={14} /></button>
        </div>
      )}

      <TopControlBar
        year={year}
        month={month}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onGenerate={handleGenerate}
        generating={generating}
        criticalCount={criticalCount}
        warningCount={warningCount}
        onShowConflicts={() => setShowConflicts(!showConflicts)}
        onAddLeave={() => setShowLeaveModal(true)}
        onOpenConfig={() => setShowConfigModal(true)}
        filterPod={filterPod}
        setFilterPod={setFilterPod}
        pods={pods}
        filterConflictsOnly={filterConflictsOnly}
        setFilterConflictsOnly={setFilterConflictsOnly}
      />

      {/* Tab Navigation */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main content */}
        <div className="flex-1 overflow-auto p-4">
          {loading && (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
              <span className="ml-3 text-gray-500">Loading roster data...</span>
            </div>
          )}
          {!loading && (
            <>
              {activeTab === 'company' && (
                <CompanyWideView
                  rosterData={rosterData}
                  employees={employees}
                  pods={pods}
                  year={year}
                  month={month}
                  conflicts={conflicts}
                  filterPod={filterPod}
                  filterConflictsOnly={filterConflictsOnly}
                  onCellEdit={handleCellEdit}
                  brands={brands}
                  processes={processes}
                />
              )}
              {activeTab === 'pod' && (
                <PodWiseView
                  rosterData={rosterData}
                  employees={employees}
                  pods={pods}
                  year={year}
                  month={month}
                  conflicts={conflicts}
                  onCellEdit={handleCellEdit}
                  brands={brands}
                  processes={processes}
                />
              )}
              {activeTab === 'brand' && (
                <BrandWiseView
                  brandSummary={brandSummary}
                  brands={brands}
                  rosterData={rosterData}
                  year={year}
                  month={month}
                  conflicts={conflicts}
                  employees={employees}
                />
              )}
              {activeTab === 'process' && (
                <ProcessWiseView
                  processSummary={processSummary}
                  processes={processes}
                  year={year}
                  month={month}
                />
              )}
              {activeTab === 'employee' && (
                <EmployeeWiseView
                  rosterData={rosterData}
                  employees={employees}
                  pods={pods}
                  year={year}
                  month={month}
                  selectedEmployee={selectedEmployee}
                  setSelectedEmployee={setSelectedEmployee}
                  conflicts={conflicts}
                />
              )}
            </>
          )}
        </div>

        {/* Conflicts Panel */}
        {showConflicts && (
          <div className="w-80 bg-white border-l border-gray-200 overflow-auto flex-shrink-0">
            <ConflictsPanel
              conflicts={conflicts}
              onResolve={handleResolveConflict}
              onClose={() => setShowConflicts(false)}
            />
          </div>
        )}
      </div>

      {showLeaveModal && (
        <AddLeaveModal
          employees={employees}
          onClose={() => setShowLeaveModal(false)}
          onSave={handleLeaveAdded}
        />
      )}

      {showConfigModal && (
        <ConfigModal
          pods={pods}
          brands={brands}
          processes={processes}
          employees={employees}
          onClose={() => setShowConfigModal(false)}
          onRefreshData={() => {
            fetchStaticData()
            fetchRosterData()
          }}
        />
      )}
    </div>
  )
}
