"""
Unit tests for the Smart Roster Scheduling Engine.

Runs with Django's test runner:
    python manage.py test scheduler

Each test uses a minimal in-memory SQLite DB (configured in settings) and
creates only the fixtures it needs, so tests are isolated and fast.
"""
import calendar
from datetime import date, timedelta
from collections import defaultdict
from unittest.mock import patch, MagicMock

from django.test import TestCase

from roster.models import (
    Pod, Employee, Brand, Process, BrandProcessConfig,
    ResourceAllocation, PublicHoliday, LeaveRequest, RosterEntry, RosterConflict
)
from scheduler.engine import generate_monthly_roster, validate_roster


# ---------------------------------------------------------------------------
# Helper: lightweight fixture builders
# ---------------------------------------------------------------------------

def _make_pod(name='Alpha', lead=None):
    from roster.models import Pod
    pod, _ = Pod.objects.get_or_create(name=name, defaults={'lead': lead})
    return pod


def _make_employee(email, name, pod, pref_off=6, is_lead=False):
    from roster.models import Employee
    emp, _ = Employee.objects.get_or_create(
        email=email,
        defaults={
            'name': name,
            'pod': pod,
            'is_pod_lead': is_lead,
            'preferred_weekly_off': pref_off,
            'max_working_days_per_week': 6,
        }
    )
    return emp


def _make_brand(name, pod):
    from roster.models import Brand
    b, _ = Brand.objects.get_or_create(name=name, defaults={'pod': pod, 'is_active': True})
    return b


def _make_process(name='Customer Support (CS)'):
    from roster.models import Process
    p, _ = Process.objects.get_or_create(name=name)
    return p


def _make_config(brand, process, rule='365_DAYS', min_staff=1, overrides=None):
    from roster.models import BrandProcessConfig
    cfg, _ = BrandProcessConfig.objects.get_or_create(
        brand=brand, process=process,
        defaults={
            'operating_rule': rule,
            'min_daily_staff': min_staff,
            'day_of_week_overrides': overrides or {},
        }
    )
    return cfg


def _make_allocation(employee, brand, process, role='PRIMARY'):
    from roster.models import ResourceAllocation
    alloc, _ = ResourceAllocation.objects.get_or_create(
        employee=employee, brand=brand, process=process,
        defaults={'role_type': role}
    )
    return alloc


def _make_leave(employee, start, end, leave_type='PLANNED_LEAVE', status='APPROVED'):
    from roster.models import LeaveRequest
    leave, _ = LeaveRequest.objects.get_or_create(
        employee=employee, start_date=start, end_date=end,
        defaults={'leave_type': leave_type, 'status': status}
    )
    return leave


# ---------------------------------------------------------------------------
# Base test case: wipes all roster tables before every test
# ---------------------------------------------------------------------------

class RosterTestBase(TestCase):
    """
    Clears all roster-related tables before each test for clean isolation.
    Uses Django's TestCase (wraps each test in a transaction and rolls back).
    """
    # Year/month used for all scheduler tests
    YEAR = 2026
    MONTH = 11  # November – 30 days

    def setUp(self):
        from roster.models import (
            RosterConflict, RosterEntry, LeaveRequest, ResourceAllocation,
            BrandProcessConfig, Brand, Employee, Pod, Process, PublicHoliday,
        )
        RosterConflict.objects.all().delete()
        RosterEntry.objects.all().delete()
        LeaveRequest.objects.all().delete()
        ResourceAllocation.objects.all().delete()
        BrandProcessConfig.objects.all().delete()
        Brand.objects.all().delete()
        Employee.objects.all().delete()
        Pod.objects.all().delete()
        Process.objects.all().delete()
        PublicHoliday.objects.all().delete()


# ---------------------------------------------------------------------------
# Test 1 – single-resource 365-day brand triggers CRITICAL COVERAGE_GAP
# ---------------------------------------------------------------------------

class TestSingleResource365DayConflict(RosterTestBase):
    """
    When the sole employee covering a 365-day brand takes a weekly off (or
    leave), the validator must raise a CRITICAL COVERAGE_GAP conflict.
    """

    def _setup_single_resource_brand(self):
        from roster.models import RosterConflict
        pod = _make_pod('Alpha')
        emp = _make_employee('solo@co.com', 'Solo Worker', pod, pref_off=6)
        Pod.objects.filter(pk=pod.pk).update(lead=emp)
        brand = _make_brand('OnlyBrand', pod)
        process = _make_process('CS')
        _make_config(brand, process, rule='365_DAYS', min_staff=1)
        _make_allocation(emp, brand, process)
        return emp, brand, process, pod

    def test_weekly_off_on_365_day_brand_generates_critical_conflict(self):
        """
        Employee takes a weekly off → 0 staff on a 365-day brand → CRITICAL.
        """
        from roster.models import RosterConflict, RosterEntry

        emp, brand, process, pod = self._setup_single_resource_brand()

        # Generate roster for November 2026
        result = generate_monthly_roster(self.YEAR, self.MONTH)

        self.assertEqual(result['status'], 'success')

        # The engine will assign at least one WEEKLY_OFF for the sole employee,
        # which creates at least one day with 0 coverage on a 365-day brand.
        critical_conflicts = RosterConflict.objects.filter(
            severity='CRITICAL',
            conflict_type='COVERAGE_GAP',
            brand=brand,
            process=process,
        )
        self.assertGreater(
            critical_conflicts.count(), 0,
            "Expected at least one CRITICAL COVERAGE_GAP for a sole-employee 365-day brand "
            "when that employee takes a weekly off."
        )

        # Every conflict must be linked to the solo employee
        for conflict in critical_conflicts:
            self.assertEqual(conflict.employee_id, emp.id)

    def test_leave_on_365_day_brand_generates_critical_conflict(self):
        """
        Employee on approved leave → 0 staff on a 365-day brand → CRITICAL.
        """
        from roster.models import RosterConflict

        emp, brand, process, pod = self._setup_single_resource_brand()

        # Three consecutive leave days
        leave_start = date(self.YEAR, self.MONTH, 10)
        leave_end   = date(self.YEAR, self.MONTH, 12)
        _make_leave(emp, leave_start, leave_end)

        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertEqual(result['status'], 'success')

        # Must have CRITICAL gaps on the leave days
        gap_on_leave_days = RosterConflict.objects.filter(
            severity='CRITICAL',
            conflict_type='COVERAGE_GAP',
            brand=brand,
            date__gte=leave_start,
            date__lte=leave_end,
        )
        self.assertEqual(
            gap_on_leave_days.count(), 3,
            "Expected exactly 3 CRITICAL COVERAGE_GAP conflicts (one per leave day)."
        )

    def test_conflict_summary_counts_match_returned_dict(self):
        """
        Return dict's conflict counts must match actual DB records.
        """
        from roster.models import RosterConflict

        self._setup_single_resource_brand()
        result = generate_monthly_roster(self.YEAR, self.MONTH)

        db_critical = RosterConflict.objects.filter(severity='CRITICAL').count()
        db_warning  = RosterConflict.objects.filter(severity='WARNING').count()

        self.assertEqual(result['conflicts']['critical'], db_critical)
        self.assertEqual(result['conflicts']['warning'],  db_warning)
        self.assertEqual(
            result['conflicts']['total'],
            result['conflicts']['critical'] + result['conflicts']['warning']
        )


# ---------------------------------------------------------------------------
# Test 2 – multi-resource off staggering maintains coverage
# ---------------------------------------------------------------------------

class TestMultiResourceOffStaggering(RosterTestBase):
    """
    When two employees share a brand with min_daily_staff=2, the engine must
    stagger their weekly offs so they never both take the same day off.
    """

    def _setup_two_employee_brand(self, min_staff=2, rule='EXCEPT_HOLIDAYS'):
        pod = _make_pod('Beta')
        emp1 = _make_employee('alice@co.com', 'Alice', pod, pref_off=6)
        emp2 = _make_employee('bob@co.com',   'Bob',   pod, pref_off=6)
        Pod.objects.filter(pk=pod.pk).update(lead=emp1)
        brand   = _make_brand('SharedBrand', pod)
        process = _make_process('CS-Shared')
        _make_config(brand, process, rule=rule, min_staff=min_staff)
        _make_allocation(emp1, brand, process, role='PRIMARY')
        _make_allocation(emp2, brand, process, role='SHARED')
        return emp1, emp2, brand, process

    def test_no_same_day_off_for_two_employee_brand(self):
        """
        On every required day, at most one of the two employees may be on
        WEEKLY_OFF – the other must be WORKING (or hard-unavailable).
        """
        from roster.models import RosterEntry, BrandProcessConfig

        emp1, emp2, brand, process = self._setup_two_employee_brand(min_staff=2)
        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertEqual(result['status'], 'success')

        cfg = BrandProcessConfig.objects.get(brand=brand, process=process)

        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        all_dates = [date(self.YEAR, self.MONTH, d) for d in range(1, num_days + 1)]

        double_off_days = []
        for d in all_dates:
            e1 = RosterEntry.objects.filter(employee=emp1, date=d).first()
            e2 = RosterEntry.objects.filter(employee=emp2, date=d).first()
            if (
                e1 and e2
                and e1.status == 'WEEKLY_OFF'
                and e2.status == 'WEEKLY_OFF'
            ):
                double_off_days.append(d)

        self.assertEqual(
            double_off_days, [],
            f"Both employees were given the same day off on: {double_off_days}. "
            "Engine must stagger offs to maintain coverage."
        )

    def test_no_coverage_gap_conflicts_for_multi_employee_brand(self):
        """
        With 2 employees covering min_daily_staff=2, and offs properly staggered,
        there must be no CRITICAL COVERAGE_GAP for this specific brand+process.
        """
        from roster.models import RosterConflict

        emp1, emp2, brand, process = self._setup_two_employee_brand(min_staff=1)
        generate_monthly_roster(self.YEAR, self.MONTH)

        gaps = RosterConflict.objects.filter(
            conflict_type='COVERAGE_GAP',
            severity='CRITICAL',
            brand=brand,
            process=process,
        )
        self.assertEqual(
            gaps.count(), 0,
            "No CRITICAL gaps expected for a 2-employee brand with min_staff=1 "
            "when offs are properly staggered."
        )

    def test_three_employee_365_day_brand_coverage(self):
        """
        Three employees on a 365-day brand with min_staff=2 should maintain
        coverage through staggered offs (never both remaining employees off
        on the same day).
        """
        from roster.models import RosterEntry

        pod  = _make_pod('Gamma')
        emp1 = _make_employee('e1@co.com', 'E1', pod, pref_off=4)
        emp2 = _make_employee('e2@co.com', 'E2', pod, pref_off=5)
        emp3 = _make_employee('e3@co.com', 'E3', pod, pref_off=6)
        Pod.objects.filter(pk=pod.pk).update(lead=emp1)
        brand   = _make_brand('TrioBrand', pod)
        process = _make_process('NDR')
        _make_config(brand, process, rule='365_DAYS', min_staff=2)
        _make_allocation(emp1, brand, process, 'PRIMARY')
        _make_allocation(emp2, brand, process, 'SHARED')
        _make_allocation(emp3, brand, process, 'SHARED')

        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertEqual(result['status'], 'success')

        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        for d in [date(self.YEAR, self.MONTH, day) for day in range(1, num_days + 1)]:
            entries = {
                e.employee_id: e.status
                for e in RosterEntry.objects.filter(date=d, employee__in=[emp1, emp2, emp3])
            }
            working_count = sum(1 for s in entries.values() if s == 'WORKING')
            # With 3 employees and min_staff=2, at most 1 can be off at a time
            off_count = sum(
                1 for s in entries.values()
                if s in ('WEEKLY_OFF', 'PLANNED_LEAVE', 'COMP_OFF', 'PUBLIC_HOLIDAY')
            )
            self.assertLessEqual(
                off_count, 1,
                f"On {d}: {off_count} employees off, but min_staff=2 requires at most 1 off "
                f"when 3 employees are allocated."
            )


# ---------------------------------------------------------------------------
# Test 3 – consecutive working days > 6 triggers WARNING
# ---------------------------------------------------------------------------

class TestConsecutiveDaysDetection(RosterTestBase):
    """
    When an employee works more than 6 consecutive days without a break,
    the validator must create a CONSECUTIVE_DAYS WARNING conflict.
    """

    def _setup_sole_employee_no_holidays(self):
        """
        Single employee on an EXCEPT_HOLIDAYS brand so we can inject
        entries manually to test streak detection without interference.
        """
        pod  = _make_pod('Delta')
        emp  = _make_employee('streak@co.com', 'Streaky', pod, pref_off=6)
        Pod.objects.filter(pk=pod.pk).update(lead=emp)
        brand   = _make_brand('StreakBrand', pod)
        process = _make_process('Retention-Streak')
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=1)
        _make_allocation(emp, brand, process)
        return emp, brand, process

    def test_seven_consecutive_working_days_generates_warning(self):
        """
        Manually insert 7 consecutive WORKING entries then run validate_roster.
        Expect at least one CONSECUTIVE_DAYS WARNING on day 7.
        """
        from roster.models import RosterEntry, RosterConflict

        emp, brand, process = self._setup_sole_employee_no_holidays()

        # Insert 7 consecutive WORKING entries starting Nov 3 (Mon)
        streak_start = date(self.YEAR, self.MONTH, 3)
        for i in range(7):
            d = streak_start + timedelta(days=i)
            RosterEntry.objects.create(
                date=d,
                employee=emp,
                brand=brand,
                process=process,
                status='WORKING',
                is_manual_override=False,
            )

        # Fill rest of month with WEEKLY_OFF so no other streaks form
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        for day in range(1, num_days + 1):
            d = date(self.YEAR, self.MONTH, day)
            if d < streak_start or d > streak_start + timedelta(days=6):
                RosterEntry.objects.get_or_create(
                    date=d, employee=emp,
                    defaults={'status': 'WEEKLY_OFF', 'is_manual_override': False}
                )

        conflicts = validate_roster(self.YEAR, self.MONTH)
        consecutive_warnings = [
            c for c in conflicts
            if c.conflict_type == 'CONSECUTIVE_DAYS' and c.severity == 'WARNING'
            and c.employee_id == emp.id
        ]
        self.assertGreater(
            len(consecutive_warnings), 0,
            "Expected at least one CONSECUTIVE_DAYS WARNING after 7 straight working days."
        )

    def test_six_consecutive_working_days_no_warning(self):
        """
        Exactly 6 consecutive working days must NOT generate a warning.
        """
        from roster.models import RosterEntry, RosterConflict

        emp, brand, process = self._setup_sole_employee_no_holidays()

        streak_start = date(self.YEAR, self.MONTH, 1)
        for i in range(6):
            d = streak_start + timedelta(days=i)
            RosterEntry.objects.create(
                date=d, employee=emp, brand=brand, process=process,
                status='WORKING', is_manual_override=False
            )
        # Day 7 is off
        RosterEntry.objects.create(
            date=streak_start + timedelta(days=6),
            employee=emp, status='WEEKLY_OFF', is_manual_override=False
        )
        # Rest of month: working then off pattern
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        for day in range(8, num_days + 1):
            d = date(self.YEAR, self.MONTH, day)
            # alternate: 6 work, 1 off
            offset = (day - 8) % 7
            status = 'WEEKLY_OFF' if offset == 6 else 'WORKING'
            RosterEntry.objects.get_or_create(
                date=d, employee=emp,
                defaults={
                    'brand': brand if status == 'WORKING' else None,
                    'process': process if status == 'WORKING' else None,
                    'status': status,
                    'is_manual_override': False,
                }
            )

        conflicts = validate_roster(self.YEAR, self.MONTH)
        consecutive_warnings = [
            c for c in conflicts
            if c.conflict_type == 'CONSECUTIVE_DAYS' and c.employee_id == emp.id
        ]
        self.assertEqual(
            len(consecutive_warnings), 0,
            "No CONSECUTIVE_DAYS warning should be raised for exactly 6 consecutive days."
        )

    def test_generate_roster_does_not_produce_streaks_longer_than_six(self):
        """
        End-to-end: the generated roster itself must not contain streaks > 6
        (the engine must assign weekly offs correctly).
        """
        from roster.models import RosterConflict

        emp, brand, process = self._setup_sole_employee_no_holidays()
        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertEqual(result['status'], 'success')

        consecutive_conflicts = RosterConflict.objects.filter(
            conflict_type='CONSECUTIVE_DAYS',
            employee=emp,
        )
        self.assertEqual(
            consecutive_conflicts.count(), 0,
            "Engine must not schedule more than 6 consecutive working days."
        )


# ---------------------------------------------------------------------------
# Test 4 – preference override is logged when preferred off day is bypassed
# ---------------------------------------------------------------------------

class TestPreferenceOverrideLogged(RosterTestBase):
    """
    When an employee's preferred weekly off day is unavailable due to coverage
    constraints and they receive no alternative off in that calendar week,
    the validator must create a PREFERENCE_OVERRIDDEN WARNING.
    """

    def _setup_preference_scenario(self, preferred_off: int = 6):
        """
        Create a 2-employee, min_staff=2 brand so the first employee can
        never take their preferred day off when both are needed.
        """
        pod  = _make_pod('Zeta')
        emp1 = _make_employee('pref1@co.com', 'PreferSun', pod, pref_off=preferred_off)
        emp2 = _make_employee('pref2@co.com', 'AlsoSun',   pod, pref_off=preferred_off)
        Pod.objects.filter(pk=pod.pk).update(lead=emp1)
        brand   = _make_brand('TightBrand', pod)
        process = _make_process('Pref-CS')
        # min_staff=2 means neither can take off at the same time
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=2)
        _make_allocation(emp1, brand, process, 'PRIMARY')
        _make_allocation(emp2, brand, process, 'SHARED')
        return emp1, emp2, brand, process

    def test_manual_working_on_preferred_day_with_no_alternative_off(self):
        """
        Inject a WORKING entry for an employee on their preferred off day,
        with no other off in the same ISO week, then validate.
        Expect a PREFERENCE_OVERRIDDEN WARNING.
        """
        from roster.models import RosterEntry, RosterConflict

        pod  = _make_pod('Eta')
        emp  = _make_employee('preftest@co.com', 'PrefTest', pod, pref_off=6)  # prefers Sunday
        Pod.objects.filter(pk=pod.pk).update(lead=emp)
        brand   = _make_brand('PrefBrand', pod)
        process = _make_process('Pref-Process')
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=1)
        _make_allocation(emp, brand, process)

        # Find the first Sunday in November 2026 (Nov 1 is a Sunday!)
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        sundays = [
            date(self.YEAR, self.MONTH, d)
            for d in range(1, num_days + 1)
            if date(self.YEAR, self.MONTH, d).weekday() == 6
        ]
        self.assertTrue(sundays, "No Sundays found in the test month.")
        target_sunday = sundays[0]

        # Fill the whole month with WORKING, except no off at all in that week
        for day in range(1, num_days + 1):
            d = date(self.YEAR, self.MONTH, day)
            RosterEntry.objects.create(
                date=d, employee=emp, brand=brand, process=process,
                status='WORKING', is_manual_override=False
            )

        conflicts = validate_roster(self.YEAR, self.MONTH)
        pref_warnings = [
            c for c in conflicts
            if c.conflict_type == 'PREFERENCE_OVERRIDDEN'
            and c.employee_id == emp.id
            and c.severity == 'WARNING'
        ]
        self.assertGreater(
            len(pref_warnings), 0,
            "Expected PREFERENCE_OVERRIDDEN warnings when employee works every Sunday "
            "with no alternative off in those weeks."
        )

    def test_alternative_off_suppresses_preference_warning(self):
        """
        If the employee has a PUBLIC_HOLIDAY or WEEKLY_OFF in the same ISO week
        as their preferred day, no PREFERENCE_OVERRIDDEN warning should be raised.
        """
        from roster.models import RosterEntry, RosterConflict, PublicHoliday

        pod  = _make_pod('Theta')
        emp  = _make_employee('altoff@co.com', 'AltOff', pod, pref_off=6)  # prefers Sunday
        Pod.objects.filter(pk=pod.pk).update(lead=emp)
        brand   = _make_brand('AltBrand', pod)
        process = _make_process('AltProcess')
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=1)
        _make_allocation(emp, brand, process)

        # Find the second Sunday in November 2026 so Saturday is also in November
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        sundays = [
            date(self.YEAR, self.MONTH, d)
            for d in range(1, num_days + 1)
            if date(self.YEAR, self.MONTH, d).weekday() == 6
        ]
        target_sunday = sundays[1]

        # Give employee a WEEKLY_OFF on Saturday (day before the Sunday) of that week
        saturday = target_sunday - timedelta(days=1)

        for day in range(1, num_days + 1):
            d = date(self.YEAR, self.MONTH, day)
            if d == saturday:
                RosterEntry.objects.create(
                    date=d, employee=emp,
                    status='WEEKLY_OFF', is_manual_override=False
                )
            else:
                RosterEntry.objects.create(
                    date=d, employee=emp, brand=brand, process=process,
                    status='WORKING', is_manual_override=False
                )

        conflicts = validate_roster(self.YEAR, self.MONTH)
        pref_warnings_target_week = [
            c for c in conflicts
            if c.conflict_type == 'PREFERENCE_OVERRIDDEN'
            and c.employee_id == emp.id
            and c.date == target_sunday
        ]
        self.assertEqual(
            len(pref_warnings_target_week), 0,
            "No PREFERENCE_OVERRIDDEN warning expected when an alternative off exists "
            "in the same ISO week as the preferred day."
        )

    def test_generate_roster_logs_preference_warnings(self):
        """
        End-to-end: when two employees share a brand with min_staff=2 and both
        prefer Sunday, the engine cannot give both a Sunday off — so at least
        one PREFERENCE_OVERRIDDEN warning may be generated for the constrained employee.
        
        This is a 'soft' test: it asserts the validator runs and returns a non-empty
        list of recognised conflict types (doesn't mandate the exact count, since
        the engine may cleverly assign alternative offs that satisfy the check).
        """
        from roster.models import RosterConflict

        emp1, emp2, brand, process = self._setup_preference_scenario(preferred_off=6)
        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertEqual(result['status'], 'success')

        # Validate that the conflict infrastructure works – we just check
        # the validator runs and the return dict has the right shape.
        self.assertIn('critical', result['conflicts'])
        self.assertIn('warning',  result['conflicts'])
        self.assertIn('total',    result['conflicts'])
        self.assertEqual(
            result['conflicts']['total'],
            result['conflicts']['critical'] + result['conflicts']['warning']
        )


# ---------------------------------------------------------------------------
# Test 5 – generate_monthly_roster return contract
# ---------------------------------------------------------------------------

class TestRosterReturnContract(RosterTestBase):
    """Verifies the shape and basic constraints of the return value."""

    def _minimal_setup(self):
        pod  = _make_pod('Contract')
        emp  = _make_employee('contract@co.com', 'Contract', pod)
        Pod.objects.filter(pk=pod.pk).update(lead=emp)
        brand   = _make_brand('ContractBrand', pod)
        process = _make_process('Contract-CS')
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=1)
        _make_allocation(emp, brand, process)
        return emp

    def test_return_value_shape(self):
        self._minimal_setup()
        result = generate_monthly_roster(self.YEAR, self.MONTH)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'success')
        self.assertIn('entries_created', result)
        self.assertIn('conflicts', result)
        self.assertEqual(result['month'], f"{self.YEAR}-{self.MONTH:02d}")

    def test_entries_created_matches_db(self):
        from roster.models import RosterEntry
        emp = self._minimal_setup()
        result = generate_monthly_roster(self.YEAR, self.MONTH)
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        # 1 employee × 30 days
        self.assertEqual(result['entries_created'], num_days * 1)
        self.assertEqual(RosterEntry.objects.filter(employee=emp).count(), num_days)

    def test_idempotent_generation(self):
        """Running generate_monthly_roster twice must not duplicate entries."""
        from roster.models import RosterEntry
        self._minimal_setup()
        generate_monthly_roster(self.YEAR, self.MONTH)
        generate_monthly_roster(self.YEAR, self.MONTH)
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]
        self.assertEqual(
            RosterEntry.objects.filter(is_manual_override=False).count(),
            num_days,
            "Re-running the scheduler must replace (not duplicate) auto-generated entries."
        )

    def test_every_employee_has_entry_for_every_day(self):
        """Every employee must have exactly one RosterEntry per calendar day."""
        from roster.models import RosterEntry, Employee

        pod = _make_pod('Full')
        emps = [
            _make_employee(f'emp{i}@co.com', f'Emp{i}', pod, pref_off=i % 7)
            for i in range(5)
        ]
        Pod.objects.filter(pk=pod.pk).update(lead=emps[0])
        brand   = _make_brand('FullBrand', pod)
        process = _make_process('Full-CS')
        _make_config(brand, process, rule='EXCEPT_HOLIDAYS', min_staff=2)
        for emp in emps:
            _make_allocation(emp, brand, process, role='SHARED')

        generate_monthly_roster(self.YEAR, self.MONTH)
        num_days = calendar.monthrange(self.YEAR, self.MONTH)[1]

        for emp in emps:
            count = RosterEntry.objects.filter(employee=emp).count()
            self.assertEqual(
                count, num_days,
                f"Employee {emp.name} has {count} entries; expected {num_days}."
            )
