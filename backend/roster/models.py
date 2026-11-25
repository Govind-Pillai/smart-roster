"""Models for the Smart Roster Management System."""

from django.db import models


# ---------------------------------------------------------------------------
# Pod
# ---------------------------------------------------------------------------
class Pod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    lead = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='led_pod',
    )

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class Employee(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    pod = models.ForeignKey(Pod, on_delete=models.CASCADE, related_name='members')
    is_pod_lead = models.BooleanField(default=False)
    max_working_days_per_week = models.IntegerField(default=6)
    preferred_weekly_off = models.IntegerField(
        default=6,
        help_text="Day of week for preferred weekly off: 0=Mon … 6=Sun",
    )

    def __str__(self):
        return f"{self.name} ({self.pod.name})"


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class Brand(models.Model):
    name = models.CharField(max_length=150, unique=True)
    pod = models.ForeignKey(Pod, on_delete=models.CASCADE, related_name='brands')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------
class Process(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# BrandProcessConfig
# ---------------------------------------------------------------------------
OPERATING_RULES = [
    ('365_DAYS', '365 Days'),
    ('EXCEPT_HOLIDAYS', 'Except Holidays'),
    ('NO_SUNDAYS_OR_HOLIDAYS', 'No Sundays or Holidays'),
]


class BrandProcessConfig(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='process_configs')
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='brand_configs')
    operating_rule = models.CharField(
        max_length=30, choices=OPERATING_RULES, default='EXCEPT_HOLIDAYS'
    )
    min_daily_staff = models.IntegerField(default=1)
    # e.g. {0: 2, 6: 0}  — day-of-week (0=Mon) → override min_daily_staff
    day_of_week_overrides = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('brand', 'process')

    def __str__(self):
        return f"{self.brand.name} / {self.process.name}"


# ---------------------------------------------------------------------------
# ResourceAllocation
# ---------------------------------------------------------------------------
ROLE_TYPES = [
    ('PRIMARY', 'Primary'),
    ('SHARED', 'Shared'),
    ('BACKUP', 'Backup'),
]


class ResourceAllocation(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='allocations')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='allocations')
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='allocations')
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES, default='PRIMARY')

    class Meta:
        unique_together = ('employee', 'brand', 'process')

    def __str__(self):
        return f"{self.employee.name} → {self.brand.name}/{self.process.name} ({self.role_type})"


# ---------------------------------------------------------------------------
# PublicHoliday
# ---------------------------------------------------------------------------
class PublicHoliday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=150)
    is_mandatory = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.date})"


# ---------------------------------------------------------------------------
# LeaveRequest
# ---------------------------------------------------------------------------
LEAVE_TYPES = [
    ('PLANNED_LEAVE', 'Planned Leave'),
    ('COMP_OFF', 'Comp Off'),
    ('UNAVAILABLE', 'Unavailable'),
]

LEAVE_STATUSES = [
    ('APPROVED', 'Approved'),
    ('PENDING', 'Pending'),
]


class LeaveRequest(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    status = models.CharField(max_length=20, choices=LEAVE_STATUSES, default='PENDING')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.employee.name}: {self.leave_type} "
            f"({self.start_date} → {self.end_date}) [{self.status}]"
        )


# ---------------------------------------------------------------------------
# RosterEntry
# ---------------------------------------------------------------------------
ROSTER_STATUSES = [
    ('WORKING', 'Working'),
    ('WEEKLY_OFF', 'Weekly Off'),
    ('PUBLIC_HOLIDAY', 'Public Holiday'),
    ('PLANNED_LEAVE', 'Planned Leave'),
    ('COMP_OFF', 'Comp Off'),
]


class RosterEntry(models.Model):
    date = models.DateField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='roster_entries')
    brand = models.ForeignKey(
        Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name='roster_entries'
    )
    process = models.ForeignKey(
        Process, null=True, blank=True, on_delete=models.SET_NULL, related_name='roster_entries'
    )
    status = models.CharField(max_length=20, choices=ROSTER_STATUSES, default='WORKING')
    is_manual_override = models.BooleanField(default=False)

    class Meta:
        unique_together = ('date', 'employee')
        ordering = ['date', 'employee__name']

    def __str__(self):
        return f"{self.employee.name} on {self.date}: {self.status}"


# ---------------------------------------------------------------------------
# RosterConflict
# ---------------------------------------------------------------------------
SEVERITY_CHOICES = [
    ('CRITICAL', 'Critical'),
    ('WARNING', 'Warning'),
]

CONFLICT_TYPES = [
    ('COVERAGE_GAP', 'Coverage Gap'),
    ('OVERALLOCATION', 'Overallocation'),
    ('CONSECUTIVE_DAYS', 'Consecutive Days'),
    ('PREFERENCE_OVERRIDDEN', 'Preference Overridden'),
]


class RosterConflict(models.Model):
    month = models.CharField(max_length=7)  # YYYY-MM
    date = models.DateField(null=True, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    conflict_type = models.CharField(max_length=30, choices=CONFLICT_TYPES)
    brand = models.ForeignKey(
        Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name='conflicts'
    )
    process = models.ForeignKey(
        Process, null=True, blank=True, on_delete=models.SET_NULL, related_name='conflicts'
    )
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name='conflicts'
    )
    description = models.TextField()
    suggested_resolution = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', 'date']

    def __str__(self):
        return f"[{self.severity}] {self.conflict_type} on {self.date or self.month}"
