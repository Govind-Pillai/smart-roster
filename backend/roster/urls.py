"""URL routing for the roster app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'pods', views.PodViewSet)
router.register(r'employees', views.EmployeeViewSet)
router.register(r'brands', views.BrandViewSet)
router.register(r'processes', views.ProcessViewSet)
router.register(r'brand-process-configs', views.BrandProcessConfigViewSet)
router.register(r'resource-allocations', views.ResourceAllocationViewSet)
router.register(r'public-holidays', views.PublicHolidayViewSet)
router.register(r'leave-requests', views.LeaveRequestViewSet)
router.register(r'roster-entries', views.RosterEntryViewSet)
router.register(r'conflicts', views.ConflictViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path(
        'roster/generate/',
        views.RosterViewSet.as_view({'post': 'generate'}),
        name='roster-generate',
    ),
    path(
        'roster/monthly/',
        views.RosterViewSet.as_view({'get': 'monthly_view'}),
        name='roster-monthly',
    ),
    path(
        'roster/validate/',
        views.RosterViewSet.as_view({'post': 'validate_roster'}),
        name='roster-validate',
    ),
    path(
        'roster/brand-summary/',
        views.RosterViewSet.as_view({'get': 'brand_summary'}),
        name='roster-brand-summary',
    ),
    path(
        'roster/employee-summary/',
        views.RosterViewSet.as_view({'get': 'employee_summary'}),
        name='roster-employee-summary',
    ),
    path(
        'roster/process-summary/',
        views.RosterViewSet.as_view({'get': 'process_summary'}),
        name='roster-process-summary',
    ),
]
