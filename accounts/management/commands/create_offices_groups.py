from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from accounts.models import Office, User
from accounts.models import OfficeAssignment

class Command(BaseCommand):
    help = 'Create all NAMETS offices, groups, and assign permissions'

    def handle(self, *args, **options):
        # 1. Create Groups
        groups_data = [
            'ICT Team',
            'Executive Team',
            'Finance Team',
            'Media Team',
            "Da'awah Team",
            'Welfare Team',
            'Business Team',
            'Events Team',
            'Academics Team',
            'Masjid Team',
            "Sisters' Team",
        ]
        groups = {}
        for gname in groups_data:
            group, created = Group.objects.get_or_create(name=gname)
            if created:
                self.stdout.write(f"Created group: {gname}")
            groups[gname] = group

        # 2. Define office data
        offices_data = [
            # (name, description, duties, icon, is_protected, linked_group_name, is_custom, template)
            ('ICT Head', 'Chief technology officer. Manages all technical infrastructure and digital information.',
             "• Oversee website and systems\n• Manage user accounts\n• Ensure security compliance\n• Provide technical support to EXCO\n• Handles hardware teachnology if needed\n• since there is no librarian office, they will manage all relavant information in digital library",
             '🖥️', True, 'ICT Team', True, 'dashboards/offices/ict_head.html'), 
            ('Wakeel', 'Chief executive officer. Presides over all EXCO meetings.',
             "• Presides over EXCO and Congress meetings\n• Chief representative and spokesman\n• Signatory to association's account\n• Final approval authority\n• Custodian of NAMETS properties\n• Chairman of Shura Committee",
             '👑', False, 'Executive Team', True, 'dashboards/offices/wakeel.html'),
            ('Deputy Wakeel', 'Deputy executive officer. Assists Wakeel.',
             "• Chairman of NAMETS Islamiyyah\n• Assists Wakeel in all duties\n• Acts for Wakeel in his absence",
             '🤝', False, 'Executive Team', True, 'dashboards/offices/deputy_wakeel.html'),
            ('Secretary General', 'Chief administrative officer.',
             "• Administrative organization\n• Summons EXCO and Congress meetings\n• Prepares agendas and minutes\n• Compiles annual reports\n• Handles correspondence",
             '📝', False, 'Executive Team', True, 'dashboards/offices/secretary_general.html'),
            ('Financial Secretary', 'Chief financial officer.',
             "• Keeps financial accounts and records\n• Ensures funds are rightly used\n• Submits monthly financial reports\n• Collects dues and contributions\n• Signatory to financial transactions\n• Chairman of Financial Committee",
             '💰', False, 'Finance Team', True, 'dashboards/offices/financial_secretary.html'),
            ('PRO I', 'Head of Public Relations.',
             "• Chairman of Publicity Committee\n• Manages association mailbox\n• Links EXCO to Ummah\n• Arranges venues\n• Acts as Master of Ceremony",
             '📢', False, 'Media Team', True, 'dashboards/offices/pro.html'),
            # Add others similarly...
            ('PRO II', 'Public Relations Officer (support).',
             "• Assist PRO I\n• Act for PRO I in his absence\n• Distribute banners and flyers",
             '📢', False, 'Media Team', False, ''),
            ('PRO III', 'Public Relations Officer (support).', "• Assist PRO I\n• Distribute banners and flyers", '📢', False, 'Media Team', False, ''),
            ('PRO IV', 'Public Relations Officer (support).', "• Assist PRO I", '📢', False, 'Media Team', False, ''),
            ('PRO V', 'Public Relations Officer (support).', "• Assist PRO I", '📢', False, 'Media Team', False, ''),
            ("Da'awah Officer I", "Head of Da'awah (Islamic outreach).",
             "• Chairman of Da'awah Committee\n• Organizes orientation programs\n• Produces annual program chart\n• Coordinates hospital/prison/graveyard visits",
             '🕌', False, "Da'awah Team", True, 'dashboards/offices/daawah.html'),
            ("Da'awah Officer II", "Da'awah Officer (support).",
             "• Assist Da'awah Officer I\n• Organize Arabic/comparative religion classes\n• Coordinate audio-visual programs",
             '🕌', False, "Da'awah Team", False, ''),
            ("Da'awah Officer III", "Da'awah Officer (support).", "• Assist Da'awah Officer I", '🕌', False, "Da'awah Team", False, ''),
            ("Da'awah Officer IV", "Da'awah Officer (support).", "• Manage sound systems", '🕌', False, "Da'awah Team", False, ''),
            ("Da'awah Officer V", "Da'awah Officer (support).", "• Manage sound systems", '🕌', False, "Da'awah Team", False, ''),
            ('Welfare Officer I', "Head of Welfare & Academic.",
             "• Chairman of Welfare/Academic Committee\n• Organizes tutorial classes\n• Manages past questions\n• Organizes final year Waleemah",
             '📚', False, 'Welfare Team', True, 'dashboards/offices/welfare.html'),
            # ... Continue all listed offices (you can expand this list with all from the table)
        ]

        # 3. Create Offices and assign groups
        for name, desc, duties, icon, is_protected, group_name, is_custom, template in offices_data:
            group = groups.get(group_name)
            office, created = Office.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'duties': duties,
                    'icon': icon,
                    'is_protected': is_protected,
                    'linked_group': group,
                    'is_custom_dashboard': is_custom,
                    'dashboard_template': template,
                }
            )
            if created:
                self.stdout.write(f"Created office: {name}")
            else:
                # Update fields if office already exists (e.g., after running command multiple times)
                office.description = desc
                office.duties = duties
                office.icon = icon
                office.is_protected = is_protected
                office.linked_group = group
                office.is_custom_dashboard = is_custom
                office.dashboard_template = template
                office.save()
                self.stdout.write(f"Updated office: {name}")

        # 4. Assign permissions to offices (example)
        # We'll assign a few key permissions based on office name
        # For simplicity, we can assign all 'view' and 'add' permissions for relevant apps to certain offices.
        # For demonstration, we'll give full permissions to ICT Head and Wakeel.
        # You can extend this as needed.

        # Let's assign all permissions to ICT Head (superuser equivalent)
        ict_office = Office.objects.get(name='ICT Head')
        all_perms = Permission.objects.all()
        ict_office.permissions.add(*all_perms)

        # Assign some permissions to Wakeel
        wakeel_office = Office.objects.get(name='Wakeel')
        # e.g., view and add permissions for communications, events, governance
        wakeel_perms = Permission.objects.filter(
            content_type__app_label__in=['communications', 'events', 'governance', 'accounts']
        )
        wakeel_office.permissions.add(*wakeel_perms)

        # PRO offices get communications permissions
        pro_office = Office.objects.get(name='PRO I')
        pro_perms = Permission.objects.filter(
            content_type__app_label='communications'
        )
        pro_office.permissions.add(*pro_perms)

        # Financial Secretary gets finance permissions (if app exists)
        # Add more as needed

        self.stdout.write(self.style.SUCCESS('All offices, groups, and permissions created/updated successfully.'))