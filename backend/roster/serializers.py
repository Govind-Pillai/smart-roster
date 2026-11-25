"""DRF serializers for the Smart Roster Management System."""

from rest_framework import serializers

from .models import (
    Pod,
    Employee,
    Brand,
    Process,
    BrandProcessConfig,
    ResourceAllocation,
    PublicHoliday,
    LeaveRequest,
    RosterEntry,
    RosterConflict,
)


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------
class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = '__all__'


# ---------------------------------------------------------------------------
# BrandProcessConfig
# ---------------------------------------------------------------------------
class BrandProcessConfigSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)

    class Meta:
        model = BrandProcessConfig
        fields = [
            'id',
            'brand',
            'brand_name',
            'process',
            'process_name',
            'operating_rule',
            'min_daily_staff',
            'day_of_week_overrides',
        ]


# ---------------------------------------------------------------------------
# Pod
# ---------------------------------------------------------------------------
class PodSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    lead_name = serializers.CharField(source='lead.name', read_only=True, default=None)

    class Meta:
        model = Pod
        fields = ['id', 'name', 'lead', 'lead_name', 'employee_count']

    def get_employee_count(self, obj):
        return obj.members.count()


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class EmployeeSerializer(serializers.ModelSerializer):
    pod_name = serializers.CharField(source='pod.name', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id',
            'name',
            'email',
            'pod',
            'pod_name',
            'is_pod_lead',
            'max_working_days_per_week',
            'preferred_weekly_off',
        ]


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class BrandSerializer(serializers.ModelSerializer):
    pod_name = serializers.CharField(source='pod.name', read_only=True)
    process_configs = BrandProcessConfigSerializer(many=True, read_only=True)

    class Meta:
        model = Brand
        fields = ['id', 'name', 'pod', 'pod_name', 'is_active', 'process_configs']


# ---------------------------------------------------------------------------
# ResourceAllocation
# ---------------------------------------------------------------------------
class ResourceAllocationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)

    class Meta:
        model = ResourceAllocation
        fields = [
            'id',
            'employee',
            'employee_name',
            'brand',
            'brand_name',
            'process',
            'process_name',
            'role_type',
        ]


# ---------------------------------------------------------------------------
# PublicHoliday
# ---------------------------------------------------------------------------
class PublicHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicHoliday
        fields = '__all__'


# ---------------------------------------------------------------------------
# LeaveRequest
# ---------------------------------------------------------------------------
class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id',
            'employee',
            'employee_name',
            'start_date',
            'end_date',
            'leave_type',
            'status',
            'notes',
            'created_at',
        ]
        read_only_fields = ['created_at']


# ---------------------------------------------------------------------------
# RosterEntry
# ---------------------------------------------------------------------------
class RosterEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_pod = serializers.CharField(source='employee.pod.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True, default=None)
    process_name = serializers.CharField(source='process.name', read_only=True, default=None)

    class Meta:
        model = RosterEntry
        fields = [
            'id',
            'date',
            'employee',
            'employee_name',
            'employee_pod',
            'brand',
            'brand_name',
            'process',
            'process_name',
            'status',
            'is_manual_override',
        ]


# ---------------------------------------------------------------------------
# RosterConflict
# ---------------------------------------------------------------------------
class RosterConflictSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True, default=None)
    process_name = serializers.CharField(source='process.name', read_only=True, default=None)
    employee_name = serializers.CharField(source='employee.name', read_only=True, default=None)

    class Meta:
        model = RosterConflict
        fields = [
            'id',
            'month',
            'date',
            'severity',
            'conflict_type',
            'brand',
            'brand_name',
            'process',
            'process_name',
            'employee',
            'employee_name',
            'description',
            'suggested_resolution',
            'resolved',
            'created_at',
        ]
        read_only_fields = ['created_at']
