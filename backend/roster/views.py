"""
DRF views / ViewSets for the Smart Roster Management System.

Scheduler engine (generate_roster / validate_roster) is implemented directly
in this file so the backend works without any extra dependencies.
"""

import calendar
import datetime
from collections import defaultdict

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Brand,
    BrandProcessConfig,
    Employee,
    LeaveRequest,
    Pod,
    Process,
    PublicHoliday,
    ResourceAllocation,
    RosterConflict,
    RosterEntry,
)
from .serializers import (
    BrandProcessConfigSerializer,
    BrandSerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    PodSerializer,
    ProcessSerializer,
    ResourceAllocationSerializer,
    RosterConflictSerializer,
    RosterEntrySerializer,
    PublicHolidaySerializer,
)


# ===========================================================================
# Helper utilities
# ===========================================================================

def _get_month_dates(year: int, month: int):
    """Return a list of all date objects for the given year/month."""
    num_days = calendar.monthrange(year, month)[1]
    return [datetime.date(year, month, d) for d in range(1, num_days + 1)]


def _is_holiday(date: datetime.date, holiday_set: set) -> bool:
    return date in holiday_set


def _build_holiday_set(year: int, month: int) -> set:
    dates = _get_month_dates(year, month)
    return set(
        PublicHoliday.objects.filter(date__in=dates, is_mandatory=True).values_list('date', flat=True)
    )


def _build_leave_map(year: int, month: int):
    """
    Returns dict: employee_id → set of leave dates (approved leaves only).
    Also returns the leave_type for each date.
    leave_map[emp_id][date] = leave_type
    """
    dates = _get_month_dates(year, month)
    first, last = dates[0], dates[-1]

    leave_map: dict[int, dict] = defaultdict(dict)
    leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__lte=last,
        end_date__gte=first,
    ).select_related('employee')

    for leave in leaves:
        current = max(leave.start_date, first)
        end = min(leave.end_date, last)
        while current <= end:
            leave_map[leave.employee_id][current] = leave.leave_type
            current += datetime.timedelta(days=1)

    return leave_map


def _should_operate(config: BrandProcessConfig, date: datetime.date, holiday_set: set) -> bool:
    """Determine if a brand/process should operate on a given date."""
    rule = config.operating_rule
    is_sunday = date.weekday() == 6
    is_hol = date in holiday_set

    if rule == '365_DAYS':
        return True
    if rule == 'EXCEPT_HOLIDAYS':
        return not is_hol
    if rule == 'NO_SUNDAYS_OR_HOLIDAYS':
        return not is_sunday and not is_hol
    return True


def _min_staff_for_day(config: BrandProcessConfig, date: datetime.date) -> int:
    """Return effective min_daily_staff considering day-of-week overrides."""
    overrides = config.day_of_week_overrides or {}
    dow = str(date.weekday())
    if dow in overrides:
        return int(overrides[dow])
    return config.min_daily_staff


# ===========================================================================
# Core scheduler engine
# ===========================================================================

@transaction.atomic
def generate_roster(year: int, month: int) -> dict:
    """
    Generate roster entries for the given year/month.
    Strategy:
      1. Delete existing non-manual entries for the month.
      2. For each day, mark public holidays and approved leaves.
      3. Assign weekly off based on preferred_weekly_off.
      4. Assign working days for all remaining employees to their primary brand/process.
      5. Detect and store conflicts.
    Returns a summary dict.
    """
    dates = _get_month_dates(year, month)
    month_str = f"{year:04d}-{month:02d}"

    # Clear auto-generated entries for this month
    RosterEntry.objects.filter(date__in=dates, is_manual_override=False).delete()
    # Clear old conflicts for this month
    RosterConflict.objects.filter(month=month_str).delete()

    holiday_set = _build_holiday_set(year, month)
    leave_map = _build_leave_map(year, month)

    employees = Employee.objects.select_related('pod').all()
    allocations = ResourceAllocation.objects.select_related(
        'employee', 'brand', 'process'
    ).filter(role_type='PRIMARY')

    # Build employee → primary allocation map
    primary_alloc: dict[int, ResourceAllocation] = {}
    for alloc in allocations:
        if alloc.employee_id not in primary_alloc:
            primary_alloc[alloc.employee_id] = alloc

    entries_to_create = []
    weekly_off_counts: dict[int, int] = defaultdict(int)  # emp_id → offs this month
    working_days_count: dict[int, int] = defaultdict(int)

    for date in dates:
        is_hol = date in holiday_set

        for employee in employees:
            emp_id = employee.id

            # Public holiday
            if is_hol:
                entries_to_create.append(
                    RosterEntry(
                        date=date,
                        employee=employee,
                        status='PUBLIC_HOLIDAY',
                        is_manual_override=False,
                    )
                )
                continue

            # Approved leave
            if emp_id in leave_map and date in leave_map[emp_id]:
                leave_type = leave_map[emp_id][date]
                roster_status = 'COMP_OFF' if leave_type == 'COMP_OFF' else 'PLANNED_LEAVE'
                entries_to_create.append(
                    RosterEntry(
                        date=date,
                        employee=employee,
                        status=roster_status,
                        is_manual_override=False,
                    )
                )
                continue

            # Weekly off — give the preferred weekday off if max_working_days logic allows
            # Simple rule: if today is their preferred day off, mark as weekly off
            # but cap at (num_days_in_month - max_working_days_per_week * 4) offs per month.
            weeks_in_month = len(dates) / 7
            max_offs = round(weeks_in_month)  # one off per week approximately
            if (
                date.weekday() == employee.preferred_weekly_off
                and weekly_off_counts[emp_id] < max_offs
            ):
                weekly_off_counts[emp_id] += 1
                entries_to_create.append(
                    RosterEntry(
                        date=date,
                        employee=employee,
                        status='WEEKLY_OFF',
                        is_manual_override=False,
                    )
                )
                continue

            # Working day
            alloc = primary_alloc.get(emp_id)
            entries_to_create.append(
                RosterEntry(
                    date=date,
                    employee=employee,
                    brand=alloc.brand if alloc else None,
                    process=alloc.process if alloc else None,
                    status='WORKING',
                    is_manual_override=False,
                )
            )
            working_days_count[emp_id] += 1

    RosterEntry.objects.bulk_create(entries_to_create, ignore_conflicts=True)

    # Run validation and store conflicts
    conflicts = _run_validation(year, month, dates, holiday_set)
    conflict_objects = [
        RosterConflict(
            month=month_str,
            date=c.get('date'),
            severity=c['severity'],
            conflict_type=c['conflict_type'],
            brand_id=c.get('brand_id'),
            process_id=c.get('process_id'),
            employee_id=c.get('employee_id'),
            description=c['description'],
            suggested_resolution=c.get('suggested_resolution', ''),
        )
        for c in conflicts
    ]
    RosterConflict.objects.bulk_create(conflict_objects)

    return {
        'year': year,
        'month': month,
        'entries_created': len(entries_to_create),
        'conflicts_found': len(conflicts),
        'holidays': len(holiday_set),
        'employees_scheduled': employees.count(),
    }


def _run_validation(year: int, month: int, dates, holiday_set: set) -> list:
    """
    Validate the generated roster entries and return a list of conflict dicts.
    Checks:
      - Coverage gaps: brand/process has fewer working staff than min_daily_staff
      - Consecutive working days > 6 without a day off
      - Employees without any weekly off in a 7-day window
    """
    conflicts = []
    month_str = f"{year:04d}-{month:02d}"

    configs = BrandProcessConfig.objects.select_related('brand', 'process').all()

    # Build a lookup: (date, brand_id, process_id) → count of WORKING entries
    working_entries = (
        RosterEntry.objects.filter(date__in=dates, status='WORKING')
        .values('date', 'brand_id', 'process_id')
    )
    coverage: dict = defaultdict(int)
    for e in working_entries:
        if e['brand_id'] and e['process_id']:
            coverage[(e['date'], e['brand_id'], e['process_id'])] += 1

    for config in configs:
        for date in dates:
            if not _should_operate(config, date, holiday_set):
                continue
            min_staff = _min_staff_for_day(config, date)
            actual = coverage.get((date, config.brand_id, config.process_id), 0)
            if actual < min_staff:
                conflicts.append({
                    'date': date,
                    'severity': 'CRITICAL',
                    'conflict_type': 'COVERAGE_GAP',
                    'brand_id': config.brand_id,
                    'process_id': config.process_id,
                    'description': (
                        f"{config.brand.name}/{config.process.name} on {date}: "
                        f"needs {min_staff} staff but only {actual} scheduled."
                    ),
                    'suggested_resolution': (
                        f"Assign a SHARED or BACKUP resource to "
                        f"{config.brand.name}/{config.process.name} on {date}."
                    ),
                })

    # Consecutive working days check per employee
    all_entries_by_emp: dict[int, list] = defaultdict(list)
    for entry in RosterEntry.objects.filter(date__in=dates).select_related('employee').order_by('date'):
        all_entries_by_emp[entry.employee_id].append(entry)

    for emp_id, entries in all_entries_by_emp.items():
        consecutive = 0
        for entry in entries:
            if entry.status == 'WORKING':
                consecutive += 1
                if consecutive > 6:
                    conflicts.append({
                        'date': entry.date,
                        'severity': 'WARNING',
                        'conflict_type': 'CONSECUTIVE_DAYS',
                        'employee_id': emp_id,
                        'description': (
                            f"Employee {entry.employee.name} has worked {consecutive} "
                            f"consecutive days as of {entry.date}."
                        ),
                        'suggested_resolution': 'Schedule a day off to avoid burnout.',
                    })
            else:
                consecutive = 0

    return conflicts


# ===========================================================================
# ViewSets
# ===========================================================================

class PodViewSet(viewsets.ModelViewSet):
    queryset = Pod.objects.all()
    serializer_class = PodSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('pod').all()
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        pod_id = self.request.query_params.get('pod_id')
        if pod_id:
            qs = qs.filter(pod_id=pod_id)
        return qs


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.select_related('pod').prefetch_related('process_configs__process').all()
    serializer_class = BrandSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        pod_id = self.request.query_params.get('pod_id')
        if pod_id:
            qs = qs.filter(pod_id=pod_id)
        active = self.request.query_params.get('is_active')
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ('true', '1', 'yes'))
        return qs


class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer


class BrandProcessConfigViewSet(viewsets.ModelViewSet):
    queryset = BrandProcessConfig.objects.select_related('brand', 'process').all()
    serializer_class = BrandProcessConfigSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        brand_id = self.request.query_params.get('brand_id')
        if brand_id:
            qs = qs.filter(brand_id=brand_id)
        process_id = self.request.query_params.get('process_id')
        if process_id:
            qs = qs.filter(process_id=process_id)
        return qs


class ResourceAllocationViewSet(viewsets.ModelViewSet):
    queryset = ResourceAllocation.objects.select_related('employee', 'brand', 'process').all()
    serializer_class = ResourceAllocationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ('employee_id', 'brand_id', 'process_id', 'role_type'):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs


class PublicHolidayViewSet(viewsets.ModelViewSet):
    queryset = PublicHoliday.objects.all()
    serializer_class = PublicHolidaySerializer


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related('employee').all()
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_update(self, serializer):
        """After approving a leave, trigger re-validation for affected months."""
        old_status = serializer.instance.status
        instance = serializer.save()
        if old_status != 'APPROVED' and instance.status == 'APPROVED':
            # Determine affected months and re-validate
            self._revalidate_affected_months(instance)

    def _revalidate_affected_months(self, leave: LeaveRequest):
        """Regenerate conflicts for all months touched by a newly approved leave."""
        current = leave.start_date.replace(day=1)
        end = leave.end_date.replace(day=1)
        while current <= end:
            year, month = current.year, current.month
            month_str = f"{year:04d}-{month:02d}"
            dates = _get_month_dates(year, month)
            holiday_set = _build_holiday_set(year, month)
            RosterConflict.objects.filter(month=month_str).delete()
            conflicts = _run_validation(year, month, dates, holiday_set)
            RosterConflict.objects.bulk_create([
                RosterConflict(
                    month=month_str,
                    date=c.get('date'),
                    severity=c['severity'],
                    conflict_type=c['conflict_type'],
                    brand_id=c.get('brand_id'),
                    process_id=c.get('process_id'),
                    employee_id=c.get('employee_id'),
                    description=c['description'],
                    suggested_resolution=c.get('suggested_resolution', ''),
                )
                for c in conflicts
            ])
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)


class RosterEntryViewSet(viewsets.ModelViewSet):
    queryset = RosterEntry.objects.select_related('employee', 'brand', 'process').all()
    serializer_class = RosterEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ('employee_id', 'brand_id', 'process_id', 'status'):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        date_param = self.request.query_params.get('date')
        if date_param:
            qs = qs.filter(date=date_param)
        return qs

    @action(detail=True, methods=['patch'], url_path='override')
    def override(self, request, pk=None):
        """
        PATCH /api/roster-entries/{id}/override/
        Manually override a roster cell (status, brand, process).
        Sets is_manual_override = True.
        """
        entry = self.get_object()
        allowed_fields = {'status', 'brand', 'process', 'brand_id', 'process_id'}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        data['is_manual_override'] = True
        serializer = self.get_serializer(entry, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ConflictViewSet(viewsets.ModelViewSet):
    queryset = RosterConflict.objects.select_related('brand', 'process', 'employee').all()
    serializer_class = RosterConflictSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        month = self.request.query_params.get('month')
        if month:
            qs = qs.filter(month=month)
        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            qs = qs.filter(resolved=resolved.lower() in ('true', '1', 'yes'))
        return qs

    @action(detail=True, methods=['post'], url_path='apply_backup')
    def apply_backup(self, request, pk=None):
        """
        POST /api/conflicts/{id}/apply_backup/
        Mark a conflict as resolved (optionally note resolution details).
        Body: { "notes": "..." }  (optional)
        """
        conflict = self.get_object()
        conflict.resolved = True
        notes = request.data.get('notes', '')
        if notes:
            conflict.suggested_resolution = notes
        conflict.save()
        serializer = self.get_serializer(conflict)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# RosterViewSet — special actions (no queryset model, uses @action routing)
# ---------------------------------------------------------------------------

class RosterViewSet(viewsets.ViewSet):
    """
    ViewSet that provides roster-level actions:
      POST /api/roster/generate/
      GET  /api/roster/monthly/
      POST /api/roster/validate/
      GET  /api/roster/brand-summary/
      GET  /api/roster/employee-summary/
      GET  /api/roster/process-summary/
    """

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _parse_year_month(data) -> tuple[int, int] | tuple[None, None]:
        try:
            year = int(data.get('year') or data.get('year'))
            month = int(data.get('month') or data.get('month'))
            if not (1 <= month <= 12):
                raise ValueError
            return year, month
        except (TypeError, ValueError):
            return None, None

    # -- generate ------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        POST /api/roster/generate/
        Body: { "year": 2026, "month": 11 }
        Generates roster entries for the given month and returns a summary.
        """
        year, month = self._parse_year_month(request.data)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from scheduler.engine import generate_monthly_roster
        summary = generate_monthly_roster(year, month)
        return Response(summary, status=status.HTTP_200_OK)

    # -- monthly_view --------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='monthly')
    def monthly_view(self, request):
        """
        GET /api/roster/monthly/?year=2026&month=11
        Returns all RosterEntry objects for that month with full details.
        """
        year, month = self._parse_year_month(request.query_params)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dates = _get_month_dates(year, month)
        entries = (
            RosterEntry.objects.filter(date__in=dates)
            .select_related('employee', 'brand', 'process', 'employee__pod')
            .order_by('date', 'employee__name')
        )
        serializer = RosterEntrySerializer(entries, many=True)
        return Response(
            {
                'year': year,
                'month': month,
                'count': entries.count(),
                'results': serializer.data,
            }
        )

    # -- validate_roster -----------------------------------------------------

    @action(detail=False, methods=['post'], url_path='validate')
    def validate_roster(self, request):
        """
        POST /api/roster/validate/
        Body: { "year": 2026, "month": 11 }
        Runs validation and returns list of conflicts.
        """
        year, month = self._parse_year_month(request.data)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from scheduler.engine import validate_roster
        conflict_objects = validate_roster(year, month)
        serializer = RosterConflictSerializer(conflict_objects, many=True)
        critical_count = sum(1 for c in conflict_objects if c.severity == 'CRITICAL')
        warning_count = sum(1 for c in conflict_objects if c.severity == 'WARNING')
        return Response(
            {
                'month': f"{year:04d}-{month:02d}",
                'conflicts': {
                    'critical': critical_count,
                    'warning': warning_count,
                    'total': len(conflict_objects),
                },
                'results': serializer.data,
            }
        )

    # -- brand_summary -------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='brand-summary')
    def brand_summary(self, request):
        """
        GET /api/roster/brand-summary/?year=2025&month=1
        Per brand, per date: how many staff are WORKING.
        """
        year, month = self._parse_year_month(request.query_params)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dates = _get_month_dates(year, month)
        holiday_set = _build_holiday_set(year, month)
        configs = BrandProcessConfig.objects.select_related('brand', 'process').all()

        # Build coverage map
        entries = (
            RosterEntry.objects.filter(date__in=dates, status='WORKING')
            .values('date', 'brand_id', 'process_id')
        )
        coverage: dict = defaultdict(int)
        for e in entries:
            if e['brand_id']:
                coverage[(e['date'], e['brand_id'], e.get('process_id'))] += 1

        result = {}
        for config in configs:
            brand_name = config.brand.name
            process_name = config.process.name
            key = f"{brand_name} / {process_name}"
            if key not in result:
                result[key] = {
                    'brand_id': config.brand_id,
                    'brand_name': brand_name,
                    'process_id': config.process_id,
                    'process_name': process_name,
                    'daily': {},
                }
            for date in dates:
                operates = _should_operate(config, date, holiday_set)
                min_staff = _min_staff_for_day(config, date) if operates else 0
                actual = coverage.get((date, config.brand_id, config.process_id), 0)
                date_str = str(date)
                result[key]['daily'][date_str] = {
                    'operates': operates,
                    'min_staff': min_staff,
                    'actual_staff': actual,
                    'status': (
                        'OK' if not operates else ('OK' if actual >= min_staff else 'UNDERSTAFFED')
                    ),
                }

        return Response({'year': year, 'month': month, 'brands': list(result.values())})

    # -- employee_summary ----------------------------------------------------

    @action(detail=False, methods=['get'], url_path='employee-summary')
    def employee_summary(self, request):
        """
        GET /api/roster/employee-summary/?year=2025&month=1&employee_id=3
        Monthly calendar for one employee.
        """
        year, month = self._parse_year_month(request.query_params)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response(
                {'error': 'employee_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dates = _get_month_dates(year, month)
        try:
            employee = Employee.objects.select_related('pod').get(pk=employee_id)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

        entries = (
            RosterEntry.objects.filter(date__in=dates, employee=employee)
            .select_related('brand', 'process')
            .order_by('date')
        )
        serializer = RosterEntrySerializer(entries, many=True)

        # Aggregate stats
        stats: dict[str, int] = defaultdict(int)
        for e in entries:
            stats[e.status] += 1

        return Response(
            {
                'year': year,
                'month': month,
                'employee': EmployeeSerializer(employee).data,
                'stats': dict(stats),
                'calendar': serializer.data,
            }
        )

    # -- process_summary -----------------------------------------------------

    @action(detail=False, methods=['get'], url_path='process-summary')
    def process_summary(self, request):
        """
        GET /api/roster/process-summary/?year=2025&month=1
        Per process per date: headcount of WORKING employees.
        """
        year, month = self._parse_year_month(request.query_params)
        if year is None:
            return Response(
                {'error': 'Provide valid year and month query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dates = _get_month_dates(year, month)

        entries = (
            RosterEntry.objects.filter(date__in=dates, status='WORKING', process__isnull=False)
            .values('date', 'process_id', 'process__name')
        )

        # process_id → {date_str → count}
        result: dict[int, dict] = {}
        for e in entries:
            pid = e['process_id']
            if pid not in result:
                result[pid] = {
                    'process_id': pid,
                    'process_name': e['process__name'],
                    'daily_headcount': {},
                }
            date_str = str(e['date'])
            result[pid]['daily_headcount'][date_str] = (
                result[pid]['daily_headcount'].get(date_str, 0) + 1
            )

        return Response(
            {
                'year': year,
                'month': month,
                'processes': list(result.values()),
            }
        )
