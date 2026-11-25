from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, timedelta
import calendar


class Command(BaseCommand):
    help = 'Seed the database with realistic roster management data'

    @transaction.atomic
    def handle(self, *args, **options):
        from roster.models import (
            Pod, Employee, Brand, Process, BrandProcessConfig,
            ResourceAllocation, PublicHoliday, LeaveRequest, RosterEntry, RosterConflict
        )

        self.stdout.write('Seeding data...')

        # Clear existing data (idempotent)
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

        # --- Processes ---
        process_names = [
            'Customer Support (CS)',
            'Abandoned Cart Conversions (ACC)',
            'Retention',
            'NDR Management',
        ]
        processes = {}
        for pname in process_names:
            p, _ = Process.objects.get_or_create(name=pname)
            processes[pname] = p

        cs = processes['Customer Support (CS)']
        acc = processes['Abandoned Cart Conversions (ACC)']
        ret = processes['Retention']
        ndr = processes['NDR Management']

        # --- Pods (created without leads first) ---
        pod_data = ['Alpha', 'Beta', 'Gamma', 'Delta']
        pods = {}
        for pname in pod_data:
            pod, _ = Pod.objects.get_or_create(name=pname, defaults={'lead': None})
            pods[pname] = pod

        # --- 32 Employees across 4 pods (8 each) ---
        # preferred_weekly_off: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        employee_data = [
            # Alpha Pod (8 employees)
            ('Arjun Sharma',       'arjun.sharma@company.com',       'Alpha', True,  6),  # Pod Lead, prefers Sun off
            ('Priya Nair',         'priya.nair@company.com',         'Alpha', False, 6),
            ('Rahul Verma',        'rahul.verma@company.com',        'Alpha', False, 0),
            ('Sneha Pillai',       'sneha.pillai@company.com',       'Alpha', False, 1),
            ('Kiran Mehta',        'kiran.mehta@company.com',        'Alpha', False, 2),
            ('Deepa Krishnan',     'deepa.krishnan@company.com',     'Alpha', False, 3),
            ('Amit Patel',         'amit.patel@company.com',         'Alpha', False, 4),
            ('Pooja Desai',        'pooja.desai@company.com',        'Alpha', False, 5),
            # Beta Pod (8 employees)
            ('Vikram Singh',       'vikram.singh@company.com',       'Beta',  True,  6),  # Pod Lead
            ('Meera Reddy',        'meera.reddy@company.com',        'Beta',  False, 6),
            ('Suresh Kumar',       'suresh.kumar@company.com',       'Beta',  False, 0),
            ('Anjali Gupta',       'anjali.gupta@company.com',       'Beta',  False, 1),
            ('Ravi Shankar',       'ravi.shankar@company.com',       'Beta',  False, 2),
            ('Nisha Joshi',        'nisha.joshi@company.com',        'Beta',  False, 3),
            ('Manoj Tiwari',       'manoj.tiwari@company.com',       'Beta',  False, 4),
            ('Kavita Rao',         'kavita.rao@company.com',         'Beta',  False, 5),
            # Gamma Pod (8 employees)
            ('Sanjay Bose',        'sanjay.bose@company.com',        'Gamma', True,  6),  # Pod Lead
            ('Lakshmi Iyer',       'lakshmi.iyer@company.com',       'Gamma', False, 6),
            ('Prakash Menon',      'prakash.menon@company.com',      'Gamma', False, 0),
            ('Divya Saxena',       'divya.saxena@company.com',       'Gamma', False, 1),
            ('Arun Kapoor',        'arun.kapoor@company.com',        'Gamma', False, 2),
            ('Sunita Chandra',     'sunita.chandra@company.com',     'Gamma', False, 3),
            ('Vinod Rastogi',      'vinod.rastogi@company.com',      'Gamma', False, 4),
            ('Geeta Pandey',       'geeta.pandey@company.com',       'Gamma', False, 5),
            # Delta Pod (8 employees)
            ('Rajesh Nambiar',     'rajesh.nambiar@company.com',     'Delta', True,  6),  # Pod Lead
            ('Uma Krishnaswamy',   'uma.krishnaswamy@company.com',   'Delta', False, 6),
            ('Harish Babu',        'harish.babu@company.com',        'Delta', False, 0),
            ('Shweta Agarwal',     'shweta.agarwal@company.com',     'Delta', False, 1),
            ('Nitin Kulkarni',     'nitin.kulkarni@company.com',     'Delta', False, 2),
            ('Rekha Bhatt',        'rekha.bhatt@company.com',        'Delta', False, 3),
            ('Sunil Ghosh',        'sunil.ghosh@company.com',        'Delta', False, 4),
            ('Anita Jain',         'anita.jain@company.com',         'Delta', False, 5),
        ]

        employees = {}
        for name, email, pod_name, is_lead, pref_off in employee_data:
            emp, _ = Employee.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'pod': pods[pod_name],
                    'is_pod_lead': is_lead,
                    'preferred_weekly_off': pref_off,
                    'max_working_days_per_week': 6,
                }
            )
            employees[email] = emp

        # Set pod leads
        Pod.objects.filter(name='Alpha').update(lead=employees['arjun.sharma@company.com'])
        Pod.objects.filter(name='Beta').update(lead=employees['vikram.singh@company.com'])
        Pod.objects.filter(name='Gamma').update(lead=employees['sanjay.bose@company.com'])
        Pod.objects.filter(name='Delta').update(lead=employees['rajesh.nambiar@company.com'])

        # --- 20 Brands ---
        # 16 single-employee brands (various pods)
        # 4 multi-employee brands
        brand_data = [
            # (name, pod, is_active)
            # Alpha pod brands
            ('FreshGlow Skincare',      'Alpha', True),
            ('UrbanFit Apparel',        'Alpha', True),
            ('PureTaste Foods',         'Alpha', True),
            ('WellNest Supplements',    'Alpha', True),
            ('StyleVault Fashion',      'Alpha', True),
            # Beta pod brands
            ('TechHome Gadgets',        'Beta',  True),
            ('PetPals Supplies',        'Beta',  True),
            ('GreenLeaf Organics',      'Beta',  True),
            ('ActiveEdge Sports',       'Beta',  True),
            ('HomeCraft Decor',         'Beta',  True),
            # Gamma pod brands
            ('BabyBloom Kids',          'Gamma', True),
            ('LuxeLife Jewelry',        'Gamma', True),
            ('QuickBite Snacks',        'Gamma', True),
            ('ClearSkin Wellness',      'Gamma', True),
            ('TravelPro Gear',          'Gamma', True),
            # Delta pod brands
            ('SmartRead Books',         'Delta', True),
            ('FitFuel Nutrition',       'Delta', True),
            ('CozyNest Bedding',        'Delta', True),
            ('GlowUp Beauty',           'Delta', True),           # multi-employee
            ('SwiftDeliver Logistics',  'Delta', True),           # multi-employee
        ]

        brands = {}
        for bname, pod_name, is_active in brand_data:
            b, _ = Brand.objects.get_or_create(
                name=bname,
                defaults={'pod': pods[pod_name], 'is_active': is_active}
            )
            brands[bname] = b

        # --- BrandProcessConfigs ---
        def make_config(brand, process, rule, min_staff=1, overrides=None):
            BrandProcessConfig.objects.get_or_create(
                brand=brand, process=process,
                defaults={
                    'operating_rule': rule,
                    'min_daily_staff': min_staff,
                    'day_of_week_overrides': overrides or {}
                }
            )

        # Alpha pod brands
        make_config(brands['FreshGlow Skincare'],   cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['FreshGlow Skincare'],   acc, '365_DAYS',              1)
        make_config(brands['UrbanFit Apparel'],     cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['UrbanFit Apparel'],     ret, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['PureTaste Foods'],      cs,  'NO_SUNDAYS_OR_HOLIDAYS', 1)
        make_config(brands['WellNest Supplements'], cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['WellNest Supplements'], ndr, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['StyleVault Fashion'],   cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['StyleVault Fashion'],   acc, 'NO_SUNDAYS_OR_HOLIDAYS', 1)

        # Beta pod brands
        make_config(brands['TechHome Gadgets'],     cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['TechHome Gadgets'],     acc, '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['PetPals Supplies'],     cs,  'NO_SUNDAYS_OR_HOLIDAYS', 1)
        make_config(brands['GreenLeaf Organics'],   cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['GreenLeaf Organics'],   ret, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['ActiveEdge Sports'],    cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['HomeCraft Decor'],      cs,  'NO_SUNDAYS_OR_HOLIDAYS', 1)
        make_config(brands['HomeCraft Decor'],      acc, 'EXCEPT_HOLIDAYS',       1)

        # Gamma pod brands
        make_config(brands['BabyBloom Kids'],       cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['LuxeLife Jewelry'],     cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['LuxeLife Jewelry'],     acc, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['QuickBite Snacks'],     cs,  'NO_SUNDAYS_OR_HOLIDAYS', 1)
        make_config(brands['ClearSkin Wellness'],   cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['TravelPro Gear'],       cs,  'EXCEPT_HOLIDAYS',       1)
        make_config(brands['TravelPro Gear'],       ndr, 'EXCEPT_HOLIDAYS',       1)

        # Delta pod brands (SmartRead, FitFuel, CozyNest are single-employee)
        make_config(brands['SmartRead Books'],      cs,  'NO_SUNDAYS_OR_HOLIDAYS', 1)
        make_config(brands['FitFuel Nutrition'],    cs,  '365_DAYS',              1)   # 365 single-emp -> CRITICAL
        make_config(brands['FitFuel Nutrition'],    acc, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['CozyNest Bedding'],     cs,  'EXCEPT_HOLIDAYS',       1)

        # Multi-employee brands
        # GlowUp Beauty: 2 employees (Sunil handles CS, Anita handles ACC+Retention), min_staff=2 on CS
        make_config(brands['GlowUp Beauty'],        cs,  'EXCEPT_HOLIDAYS',       2, {'0': 3})  # Min 2, Mon needs 3
        make_config(brands['GlowUp Beauty'],        acc, 'EXCEPT_HOLIDAYS',       1)
        make_config(brands['GlowUp Beauty'],        ret, 'EXCEPT_HOLIDAYS',       1)

        # SwiftDeliver Logistics: 3 employees sharing CS, min_staff=2
        make_config(brands['SwiftDeliver Logistics'], cs,  '365_DAYS',            2)
        make_config(brands['SwiftDeliver Logistics'], ndr, 'EXCEPT_HOLIDAYS',     1)

        # --- Resource Allocations ---
        def alloc(emp_email, brand_name, process, role='PRIMARY'):
            ResourceAllocation.objects.get_or_create(
                employee=employees[emp_email],
                brand=brands[brand_name],
                process=process,
                defaults={'role_type': role}
            )

        # Alpha pod single-employee brands
        alloc('priya.nair@company.com',      'FreshGlow Skincare',   cs)
        alloc('priya.nair@company.com',      'FreshGlow Skincare',   acc)
        alloc('rahul.verma@company.com',     'UrbanFit Apparel',     cs)
        alloc('rahul.verma@company.com',     'UrbanFit Apparel',     ret)
        alloc('sneha.pillai@company.com',    'PureTaste Foods',      cs)
        alloc('kiran.mehta@company.com',     'WellNest Supplements', cs)
        alloc('kiran.mehta@company.com',     'WellNest Supplements', ndr)
        # StyleVault: split between Amit (CS) and Pooja (ACC) - multi-employee
        alloc('amit.patel@company.com',      'StyleVault Fashion',   cs)
        alloc('pooja.desai@company.com',     'StyleVault Fashion',   acc)
        alloc('deepa.krishnan@company.com',  'StyleVault Fashion',   cs,  'SHARED')  # Also shared on CS

        # Beta pod single-employee brands
        alloc('meera.reddy@company.com',     'TechHome Gadgets',     cs)
        alloc('meera.reddy@company.com',     'TechHome Gadgets',     acc)
        alloc('suresh.kumar@company.com',    'PetPals Supplies',     cs)
        alloc('anjali.gupta@company.com',    'GreenLeaf Organics',   cs)
        alloc('anjali.gupta@company.com',    'GreenLeaf Organics',   ret)
        alloc('ravi.shankar@company.com',    'ActiveEdge Sports',    cs)
        alloc('nisha.joshi@company.com',     'HomeCraft Decor',      cs)
        alloc('nisha.joshi@company.com',     'HomeCraft Decor',      acc)
        alloc('manoj.tiwari@company.com',    'HomeCraft Decor',      cs,  'SHARED')
        alloc('kavita.rao@company.com',      'ActiveEdge Sports',    cs,  'SHARED')

        # Gamma pod single-employee brands
        alloc('lakshmi.iyer@company.com',    'BabyBloom Kids',       cs)
        alloc('prakash.menon@company.com',   'LuxeLife Jewelry',     cs)
        alloc('prakash.menon@company.com',   'LuxeLife Jewelry',     acc)
        alloc('divya.saxena@company.com',    'QuickBite Snacks',     cs)
        alloc('arun.kapoor@company.com',     'ClearSkin Wellness',   cs)
        alloc('sunita.chandra@company.com',  'TravelPro Gear',       cs)
        alloc('sunita.chandra@company.com',  'TravelPro Gear',       ndr)
        alloc('vinod.rastogi@company.com',   'QuickBite Snacks',     cs,  'SHARED')
        alloc('geeta.pandey@company.com',    'BabyBloom Kids',       cs,  'SHARED')

        # Delta pod
        alloc('harish.babu@company.com',     'SmartRead Books',      cs)
        alloc('shweta.agarwal@company.com',  'FitFuel Nutrition',    cs)
        alloc('shweta.agarwal@company.com',  'FitFuel Nutrition',    acc)
        alloc('nitin.kulkarni@company.com',  'CozyNest Bedding',     cs)
        # GlowUp Beauty: multi-employee
        alloc('sunil.ghosh@company.com',     'GlowUp Beauty',        cs)
        alloc('anita.jain@company.com',      'GlowUp Beauty',        cs,  'SHARED')
        alloc('anita.jain@company.com',      'GlowUp Beauty',        acc)
        alloc('anita.jain@company.com',      'GlowUp Beauty',        ret)
        # SwiftDeliver: 3 employees sharing
        alloc('rekha.bhatt@company.com',         'SwiftDeliver Logistics', cs)
        alloc('uma.krishnaswamy@company.com',     'SwiftDeliver Logistics', cs,  'SHARED')
        alloc('rajesh.nambiar@company.com',       'SwiftDeliver Logistics', cs,  'SHARED')  # Pod lead covering
        alloc('rekha.bhatt@company.com',          'SwiftDeliver Logistics', ndr)

        # --- Public Holidays ---
        # Current month (November 2026) and next month (December 2026)
        holidays = [
            (date(2026, 11, 26), 'Thanksgiving Day',    True),
            (date(2026, 12, 25), 'Christmas Day',       True),
            (date(2026, 12, 31), 'New Year Eve',        False),
            (date(2026, 11,  7), 'Diwali (observed)',   True),
        ]
        for hdate, hname, is_mandatory in holidays:
            PublicHoliday.objects.get_or_create(
                date=hdate,
                defaults={'name': hname, 'is_mandatory': is_mandatory}
            )

        # --- Sample Leave Requests ---
        # Approved leaves to demonstrate constraints
        leaves = [
            # Single-resource 365-day brand employee on leave -> CRITICAL
            ('priya.nair@company.com',    date(2026, 11, 28), date(2026, 11, 30), 'PLANNED_LEAVE', 'APPROVED'),
            # Multi-resource brand employee on leave -> WARNING/manageable
            ('sunil.ghosh@company.com',   date(2026, 11, 20), date(2026, 11, 22), 'PLANNED_LEAVE', 'APPROVED'),
            # Comp off
            ('rahul.verma@company.com',   date(2026, 11, 15), date(2026, 11, 15), 'COMP_OFF',      'APPROVED'),
            # Another leave in December
            ('anjali.gupta@company.com',  date(2026, 12, 22), date(2026, 12, 24), 'PLANNED_LEAVE', 'APPROVED'),
            # Pending leave (should not affect roster)
            ('arun.kapoor@company.com',   date(2026, 11, 10), date(2026, 11, 11), 'PLANNED_LEAVE', 'PENDING'),
        ]

        for emp_email, start, end, ltype, lstatus in leaves:
            LeaveRequest.objects.get_or_create(
                employee=employees[emp_email],
                start_date=start,
                end_date=end,
                defaults={'leave_type': ltype, 'status': lstatus}
            )

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded: {Pod.objects.count()} pods, '
            f'{Employee.objects.count()} employees, '
            f'{Brand.objects.count()} brands, '
            f'{Process.objects.count()} processes, '
            f'{BrandProcessConfig.objects.count()} configs, '
            f'{ResourceAllocation.objects.count()} allocations, '
            f'{PublicHoliday.objects.count()} holidays, '
            f'{LeaveRequest.objects.count()} leave requests'
        ))
