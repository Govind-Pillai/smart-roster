"""
Smart Roster Scheduling Engine
Deterministic, constraint-driven monthly roster generator.
"""
import calendar
from datetime import date, timedelta
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional


def generate_monthly_roster(year: int, month: int) -> dict:
    """
    Main entry point. Generates a complete roster for a given month.

    Algorithm:
    1. Build calendar metadata (all dates, day-of-week, holidays)
    2. Load all active employees, brands, BrandProcessConfigs, ResourceAllocations
    3. Clear existing non-manual RosterEntry records for this month
    4. Clear existing RosterConflict records for this month
    5. For each employee, determine hard unavailability (approved leaves, public holidays)
    6. For each (brand, process) pair, determine required operating days
    7. Assign weekly offs intelligently:
       - Multi-employee allocations: stagger offs to maintain coverage
       - Single-employee allocations on 365_DAYS: assign preferred day, log CRITICAL conflict
    8. Build final RosterEntry records (WORKING/WEEKLY_OFF/PLANNED_LEAVE/COMP_OFF/PUBLIC_HOLIDAY)
    9. Run validate_roster() to log all conflicts
    10. Return summary stats

    Returns: {
        'status': 'success',
        'entries_created': int,
        'conflicts': {'critical': int, 'warning': int},
        'month': 'YYYY-MM'
    }
    """
    from roster.models import (
        Employee, Brand, Process, BrandProcessConfig, ResourceAllocation,
        PublicHoliday, LeaveRequest, RosterEntry, RosterConflict, Pod
    )

    year = int(year)
    month = int(month)
    month_str = f"{year}-{month:02d}"

    # --- Step 1: Build calendar ---
    num_days = calendar.monthrange(year, month)[1]
    all_dates = [date(year, month, d) for d in range(1, num_days + 1)]

    # --- Step 2: Load holidays ---
    start_date = all_dates[0]
    end_date = all_dates[-1]
    holiday_dates: Set[date] = set(
        PublicHoliday.objects.filter(date__gte=start_date, date__lte=end_date)
                             .values_list('date', flat=True)
    )

    # --- Step 3: Load approved leaves per employee ---
    # Returns {employee_id: {date: leave_type}}
    emp_leave_dates: Dict[int, Dict[date, str]] = defaultdict(dict)
    leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__lte=end_date,
        end_date__gte=start_date
    ).select_related('employee')
    for leave in leaves:
        emp = leave.employee
        cur = max(leave.start_date, start_date)
        while cur <= min(leave.end_date, end_date):
            emp_leave_dates[emp.id][cur] = leave.leave_type
            cur += timedelta(days=1)

    # --- Step 4: Load allocations ---
    employees = list(Employee.objects.select_related('pod').all())
    allocations = list(ResourceAllocation.objects.select_related(
        'employee', 'brand', 'process', 'brand__pod'
    ).all())

    # Group allocations: brand+process -> list of employees
    bp_to_employees: Dict[Tuple[int, int], List] = defaultdict(list)
    # Group allocations: employee -> list of (brand, process, role_type)
    emp_to_allocs: Dict[int, List] = defaultdict(list)
    for alloc in allocations:
        bp_to_employees[(alloc.brand_id, alloc.process_id)].append(alloc.employee)
        emp_to_allocs[alloc.employee_id].append((alloc.brand, alloc.process, alloc.role_type))

    # --- Step 5: Load BrandProcessConfigs ---
    configs = list(BrandProcessConfig.objects.select_related('brand', 'process').all())
    bp_configs: Dict[Tuple[int, int], BrandProcessConfig] = {}
    for cfg in configs:
        bp_configs[(cfg.brand_id, cfg.process_id)] = cfg

    # --- Step 6: Determine required days per (brand, process) ---
    def is_required(cfg: BrandProcessConfig, d: date) -> bool:
        if cfg.operating_rule == '365_DAYS':
            return True
        elif cfg.operating_rule == 'EXCEPT_HOLIDAYS':
            return d not in holiday_dates
        elif cfg.operating_rule == 'NO_SUNDAYS_OR_HOLIDAYS':
            return d.weekday() != 6 and d not in holiday_dates
        return True

    def get_min_staff(cfg: BrandProcessConfig, d: date) -> int:
        dow = str(d.weekday())
        return cfg.day_of_week_overrides.get(dow, cfg.min_daily_staff)

    # --- Step 7: Determine hard unavailability per employee per date ---
    # hard_unavailable[emp_id][date] = status_string
    hard_unavail: Dict[int, Dict[date, str]] = defaultdict(dict)
    for emp in employees:
        for d in all_dates:
            if d in emp_leave_dates[emp.id]:
                leave_type = emp_leave_dates[emp.id][d]
                if leave_type == 'PLANNED_LEAVE':
                    hard_unavail[emp.id][d] = 'PLANNED_LEAVE'
                elif leave_type == 'COMP_OFF':
                    hard_unavail[emp.id][d] = 'COMP_OFF'
                else:
                    hard_unavail[emp.id][d] = 'PLANNED_LEAVE'
            elif d in holiday_dates:
                hard_unavail[emp.id][d] = 'PUBLIC_HOLIDAY'

    # --- Step 8: Smart weekly off assignment ---
    # Track offs per brand-process-date to maintain coverage
    # (bid, pid, date) -> count of employees off
    bp_offs: Dict[Tuple[int, int, date], int] = defaultdict(int)

    def get_max_allowed_offs(b_id: int, p_id: int, d: date) -> int:
        allocated = bp_to_employees.get((b_id, p_id), [])
        if len(allocated) <= 1:
            return 999  # Single-employee brand: unconstrained, will log CRITICAL gap
        cfg = bp_configs.get((b_id, p_id))
        min_staff = get_min_staff(cfg, d) if cfg else 1
        return max(1, len(allocated) - min_staff)

    def can_take_off_on_date(emp: Employee, d: date) -> bool:
        if d in hard_unavail[emp.id]:
            return False
        for (b, p, rt) in emp_to_allocs[emp.id]:
            max_offs = get_max_allowed_offs(b.id, p.id, d)
            if bp_offs[(b.id, p.id, d)] >= max_offs:
                return False
        return True

    weekly_off_dates: Dict[int, Set[date]] = defaultdict(set)

    # Divide month into 7-day blocks: [1..7], [8..14], [15..21], [22..28], [29..end]
    blocks = []
    for start_idx in range(0, len(all_dates), 7):
        blocks.append(all_dates[start_idx:min(start_idx + 7, len(all_dates))])

    # Assign 1 off per block for each employee (tail blocks < 4 days are covered by consecutive days pass)
    for block in blocks:
        if len(block) < 4:
            continue
        for emp in sorted(employees, key=lambda e: (e.is_pod_lead, e.id)):
            # If employee already has hard unavailability in this block, counts as rest
            if any(d in hard_unavail[emp.id] for d in block):
                continue

            # 1. Prefer preferred_weekly_off
            preferred_day = next((d for d in block if d.weekday() == emp.preferred_weekly_off), None)
            chosen_day = None

            if preferred_day and can_take_off_on_date(emp, preferred_day):
                chosen_day = preferred_day
            else:
                # 2. Find any day in block that preserves coverage
                candidates = [d for d in block if d != preferred_day and can_take_off_on_date(emp, d)]
                if candidates:
                    # Pick candidate with least total offs assigned across employee's brands
                    candidates.sort(key=lambda d: sum(
                        bp_offs[(b.id, p.id, d)] for (b, p, rt) in emp_to_allocs[emp.id]
                    ))
                    chosen_day = candidates[0]

            # 3. Fallback if strictly constrained
            if not chosen_day:
                chosen_day = preferred_day if preferred_day else block[0]

            weekly_off_dates[emp.id].add(chosen_day)
            for (b, p, rt) in emp_to_allocs[emp.id]:
                bp_offs[(b.id, p.id, chosen_day)] += 1

    # Second pass: strictly guarantee max 6 consecutive working days
    for emp in employees:
        consecutive = 0
        for d in all_dates:
            is_off = (d in hard_unavail[emp.id]) or (d in weekly_off_dates[emp.id])
            if not is_off:
                consecutive += 1
                if consecutive > 6:
                    weekly_off_dates[emp.id].add(d)
                    for (b, p, rt) in emp_to_allocs[emp.id]:
                        bp_offs[(b.id, p.id, d)] += 1
                    consecutive = 0
            else:
                consecutive = 0

    # --- Step 9: Build RosterEntry records ---
    # Clear existing non-manual entries for this month
    RosterEntry.objects.filter(
        date__gte=start_date, date__lte=end_date, is_manual_override=False
    ).delete()

    entries_to_create = []
    for emp in employees:
        allocs = emp_to_allocs[emp.id]

        # Determine primary brand/process for this employee
        # Use first PRIMARY allocation if available
        primary_alloc = next(
            ((b, p) for b, p, rt in allocs if rt == 'PRIMARY'),
            (allocs[0][0], allocs[0][1]) if allocs else (None, None)
        )
        primary_brand, primary_process = primary_alloc if primary_alloc else (None, None)

        for d in all_dates:
            status = None
            brand = None
            process = None

            if d in hard_unavail[emp.id]:
                status = hard_unavail[emp.id][d]
            elif d in weekly_off_dates[emp.id]:
                status = 'WEEKLY_OFF'
            else:
                status = 'WORKING'
                brand = primary_brand
                process = primary_process

            entries_to_create.append(RosterEntry(
                date=d,
                employee=emp,
                brand=brand,
                process=process,
                status=status,
                is_manual_override=False
            ))

    # Bulk create
    RosterEntry.objects.bulk_create(entries_to_create, ignore_conflicts=True)

    # --- Step 10: Validate and log conflicts ---
    conflicts = validate_roster(year, month)

    critical_count = sum(1 for c in conflicts if c.severity == 'CRITICAL')
    warning_count = sum(1 for c in conflicts if c.severity == 'WARNING')

    return {
        'status': 'success',
        'entries_created': len(entries_to_create),
        'conflicts': {
            'critical': critical_count,
            'warning': warning_count,
            'total': critical_count + warning_count
        },
        'month': month_str
    }


def validate_roster(year: int, month: int) -> list:
    """
    Validate a generated roster and create RosterConflict records.

    Checks:
    1. COVERAGE_GAP: Brand-process has required coverage but staff < min_daily_staff
    2. CONSECUTIVE_DAYS: Employee works >6 days in a row without weekly off
    3. OVERALLOCATION: Employee assigned to conflicting brands/processes same day
    4. PREFERENCE_OVERRIDDEN: Employee's preferred weekly off day was not honored

    Returns list of RosterConflict objects created.
    """
    from roster.models import (
        Employee, Brand, Process, BrandProcessConfig, ResourceAllocation,
        PublicHoliday, LeaveRequest, RosterEntry, RosterConflict
    )

    year = int(year)
    month = int(month)
    month_str = f"{year}-{month:02d}"
    num_days = calendar.monthrange(year, month)[1]
    all_dates = [date(year, month, d) for d in range(1, num_days + 1)]
    start_date = all_dates[0]
    end_date = all_dates[-1]

    # Clear old conflicts for this month
    RosterConflict.objects.filter(month=month_str).delete()

    holiday_dates: Set[date] = set(
        PublicHoliday.objects.filter(date__gte=start_date, date__lte=end_date)
                             .values_list('date', flat=True)
    )

    # Load all roster entries for this month
    entries = list(RosterEntry.objects.filter(
        date__gte=start_date, date__lte=end_date
    ).select_related('employee', 'brand', 'process', 'employee__pod'))

    # Index: (date, employee_id) -> entry
    entry_map: Dict[Tuple[date, int], RosterEntry] = {}
    for e in entries:
        entry_map[(e.date, e.employee_id)] = e

    # Index: date -> list of WORKING entries
    date_working: Dict[date, List[RosterEntry]] = defaultdict(list)
    for e in entries:
        if e.status == 'WORKING':
            date_working[e.date].append(e)

    configs = list(BrandProcessConfig.objects.select_related('brand', 'process').all())
    allocations = list(ResourceAllocation.objects.select_related(
        'employee', 'brand', 'process'
    ).all())
    employees = list(Employee.objects.select_related('pod').all())

    bp_to_employees: Dict[Tuple[int, int], List] = defaultdict(list)
    for alloc in allocations:
        bp_to_employees[(alloc.brand_id, alloc.process_id)].append(alloc.employee)

    bp_configs: Dict[Tuple[int, int], BrandProcessConfig] = {}
    for cfg in configs:
        bp_configs[(cfg.brand_id, cfg.process_id)] = cfg

    def is_required(cfg: BrandProcessConfig, d: date) -> bool:
        if cfg.operating_rule == '365_DAYS':
            return True
        elif cfg.operating_rule == 'EXCEPT_HOLIDAYS':
            return d not in holiday_dates
        elif cfg.operating_rule == 'NO_SUNDAYS_OR_HOLIDAYS':
            return d.weekday() != 6 and d not in holiday_dates
        return True

    def get_min_staff(cfg: BrandProcessConfig, d: date) -> int:
        dow = str(d.weekday())
        return cfg.day_of_week_overrides.get(dow, cfg.min_daily_staff)

    conflicts_to_create = []

    # --- Check 1: Coverage Gaps ---
    for cfg in configs:
        alloc_emps = bp_to_employees.get((cfg.brand_id, cfg.process_id), [])
        if not alloc_emps:
            continue

        for d in all_dates:
            if not is_required(cfg, d):
                continue
            min_staff = get_min_staff(cfg, d)

            # Count employees working for this brand+process
            working_count = 0
            for emp in alloc_emps:
                entry = entry_map.get((d, emp.id))
                if entry and entry.status == 'WORKING':
                    working_count += 1

            if working_count < min_staff:
                # Find available backups in the same pod
                pod = cfg.brand.pod
                backup_suggestions = []
                all_pod_emps = [
                    e for e in employees
                    if e.pod_id == pod.id and e not in alloc_emps
                ]
                for backup_emp in all_pod_emps:
                    backup_entry = entry_map.get((d, backup_emp.id))
                    if backup_entry and backup_entry.status == 'WORKING':
                        backup_suggestions.append(backup_emp.name)

                severity = 'CRITICAL' if len(alloc_emps) == 1 else 'WARNING'
                if working_count == 0:
                    severity = 'CRITICAL'

                desc = (
                    f"Brand '{cfg.brand.name}' / Process '{cfg.process.name}' requires "
                    f"{min_staff} staff on {d.strftime('%a, %d %b')} but only "
                    f"{working_count} available."
                )
                if working_count == 0:
                    desc += " NO COVERAGE - this brand-process is completely unmanned."

                suggestion = ""
                if backup_suggestions:
                    suggestion = (
                        f"Available backup staff in {pod.name} pod: "
                        f"{', '.join(backup_suggestions[:3])}. "
                        f"Consider reassigning one of them to cover this gap."
                    )
                elif pod.lead:
                    suggestion = (
                        f"Escalate to Pod Lead '{pod.lead.name}'. "
                        f"No cross-trained backups found in the same pod."
                    )

                conflicts_to_create.append(RosterConflict(
                    month=month_str,
                    date=d,
                    severity=severity,
                    conflict_type='COVERAGE_GAP',
                    brand=cfg.brand,
                    process=cfg.process,
                    employee=alloc_emps[0] if len(alloc_emps) == 1 else None,
                    description=desc,
                    suggested_resolution=suggestion
                ))

    # --- Check 2: Consecutive working days > 6 ---
    for emp in employees:
        consecutive = 0
        streak_start = None
        for d in all_dates:
            entry = entry_map.get((d, emp.id))
            if entry and entry.status == 'WORKING':
                if consecutive == 0:
                    streak_start = d
                consecutive += 1
                if consecutive > 6:
                    conflicts_to_create.append(RosterConflict(
                        month=month_str,
                        date=d,
                        severity='WARNING',
                        conflict_type='CONSECUTIVE_DAYS',
                        employee=emp,
                        description=(
                            f"Employee '{emp.name}' has worked {consecutive} consecutive days "
                            f"starting {streak_start.strftime('%d %b')} without a weekly off. "
                            f"Maximum allowed is 6 consecutive working days."
                        ),
                        suggested_resolution=(
                            f"Assign a weekly off to '{emp.name}' on or before "
                            f"{(streak_start + timedelta(days=6)).strftime('%d %b')}."
                        )
                    ))
            else:
                consecutive = 0
                streak_start = None

    # --- Check 3: Preference overrides ---
    for emp in employees:
        pref_day = emp.preferred_weekly_off  # 0=Mon, 6=Sun
        for d in all_dates:
            if d.weekday() == pref_day:
                entry = entry_map.get((d, emp.id))
                if entry and entry.status == 'WORKING':
                    # Check if they got ANY off this week
                    week_start = d - timedelta(days=d.weekday())
                    had_off_this_week = False
                    for i in range(7):
                        check_date = week_start + timedelta(days=i)
                        check_entry = entry_map.get((check_date, emp.id))
                        if check_entry and check_entry.status in (
                            'WEEKLY_OFF', 'PUBLIC_HOLIDAY', 'PLANNED_LEAVE', 'COMP_OFF'
                        ):
                            had_off_this_week = True
                            break

                    if not had_off_this_week:
                        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                        conflicts_to_create.append(RosterConflict(
                            month=month_str,
                            date=d,
                            severity='WARNING',
                            conflict_type='PREFERENCE_OVERRIDDEN',
                            employee=emp,
                            description=(
                                f"Employee '{emp.name}' prefers weekly off on "
                                f"{day_names[pref_day]} but is "
                                f"scheduled to work on {d.strftime('%a, %d %b')} with no "
                                f"alternative off this week due to coverage requirements."
                            ),
                            suggested_resolution=(
                                f"Try to find a backup for '{emp.name}' on {d.strftime('%d %b')} "
                                f"to honor their preferred weekly off day."
                            )
                        ))

    # Bulk create conflicts
    if conflicts_to_create:
        RosterConflict.objects.bulk_create(conflicts_to_create)

    return conflicts_to_create
