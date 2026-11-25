export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate()
}

export function getDateArray(year, month) {
  const days = getDaysInMonth(year, month)
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(year, month - 1, i + 1)
    return {
      date: `${year}-${String(month).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`,
      day: i + 1,
      dayOfWeek: d.getDay(), // 0=Sun, 6=Sat
      dayLabel: DAYS[(d.getDay() + 6) % 7], // Convert to Mon=0
      isSunday: d.getDay() === 0,
      isSaturday: d.getDay() === 6,
    }
  })
}

export function statusColor(status) {
  const map = {
    WORKING: 'bg-blue-100 text-blue-800 border-blue-200',
    WEEKLY_OFF: 'bg-gray-100 text-gray-600 border-gray-200',
    PUBLIC_HOLIDAY: 'bg-purple-100 text-purple-800 border-purple-200',
    PLANNED_LEAVE: 'bg-amber-100 text-amber-800 border-amber-200',
    COMP_OFF: 'bg-teal-100 text-teal-800 border-teal-200',
  }
  return map[status] || 'bg-gray-50 text-gray-400'
}

export function statusShort(status) {
  const map = {
    WORKING: 'W',
    WEEKLY_OFF: 'WO',
    PUBLIC_HOLIDAY: 'PH',
    PLANNED_LEAVE: 'PL',
    COMP_OFF: 'CO',
  }
  return map[status] || '-'
}

export function statusBg(status) {
  const map = {
    WORKING: '#DBEAFE',
    WEEKLY_OFF: '#F3F4F6',
    PUBLIC_HOLIDAY: '#EDE9FE',
    PLANNED_LEAVE: '#FEF3C7',
    COMP_OFF: '#CCFBF1',
  }
  return map[status] || '#F9FAFB'
}
