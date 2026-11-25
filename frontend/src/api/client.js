import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

export const rosterApi = {
  // Roster operations
  generate: (year, month) => api.post('/roster/generate/', { year, month }),
  getMonthly: (year, month) => api.get(`/roster/monthly/?year=${year}&month=${month}`),
  validate: (year, month) => api.post('/roster/validate/', { year, month }),
  getBrandSummary: (year, month) => api.get(`/roster/brand-summary/?year=${year}&month=${month}`),
  getEmployeeSummary: (year, month, employeeId) =>
    api.get(`/roster/employee-summary/?year=${year}&month=${month}&employee_id=${employeeId}`),
  getProcessSummary: (year, month) => api.get(`/roster/process-summary/?year=${year}&month=${month}`),

  // Entities
  getPods: () => api.get('/pods/'),
  getEmployees: () => api.get('/employees/'),
  createEmployee: (data) => api.post('/employees/', data),
  getBrands: () => api.get('/brands/'),
  createBrand: (data) => api.post('/brands/', data),
  getProcesses: () => api.get('/processes/'),
  getConfigs: () => api.get('/brand-process-configs/'),
  createConfig: (data) => api.post('/brand-process-configs/', data),
  updateConfig: (id, data) => api.patch(`/brand-process-configs/${id}/`, data),
  getAllocations: () => api.get('/resource-allocations/'),
  createAllocation: (data) => api.post('/resource-allocations/', data),
  deleteAllocation: (id) => api.delete(`/resource-allocations/${id}/`),
  getHolidays: () => api.get('/public-holidays/'),

  // Leaves
  getLeaves: () => api.get('/leave-requests/'),
  createLeave: (data) => api.post('/leave-requests/', data),
  updateLeave: (id, data) => api.patch(`/leave-requests/${id}/`, data),

  // Conflicts
  getConflicts: (month) => api.get(`/conflicts/?month=${month}`),
  resolveConflict: (id) => api.post(`/conflicts/${id}/apply_backup/`),

  // Roster entries (for cell editing)
  updateEntry: (id, data) => api.patch(`/roster-entries/${id}/`, data),
}

export default api
