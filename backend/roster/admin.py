from django.contrib import admin

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

admin.site.register(Pod)
admin.site.register(Employee)
admin.site.register(Brand)
admin.site.register(Process)
admin.site.register(BrandProcessConfig)
admin.site.register(ResourceAllocation)
admin.site.register(PublicHoliday)
admin.site.register(LeaveRequest)
admin.site.register(RosterEntry)
admin.site.register(RosterConflict)
