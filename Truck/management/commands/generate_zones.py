"""
Management command: python manage.py generate_zones

Usage:
    # Generate demo zones (synthetic Georgia data)
    docker compose exec web python manage.py generate_zones --demo

    # Generate from real job data only
    docker compose exec web python manage.py generate_zones

    # Regenerate without clearing existing zones
    docker compose exec web python manage.py generate_zones --demo --no-clear

    # Custom lookback window
    docker compose exec web python manage.py generate_zones --demo --days 60
"""
from django.core.management.base import BaseCommand
from Truck.zone_generator import generate_zones, DEMO_CITIES


class Command(BaseCommand):
    help = 'Generate DBSCAN delivery zones from historical job pickup data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo', action='store_true', default=False,
            help='Inject synthetic Georgia city data for demo presentation',
        )
        parser.add_argument(
            '--no-clear', action='store_true', default=False,
            help='Keep existing zones instead of deleting them first',
        )
        parser.add_argument(
            '--days', type=int, default=30,
            help='Lookback window in days for real job data (default: 30)',
        )

    def handle(self, *args, **options):
        demo_mode      = options['demo']
        clear_existing = not options['no_clear']
        days           = options['days']

        self.stdout.write(self.style.HTTP_INFO(
            '\n━━━ RVC DBSCAN Zone Generator ━━━'
        ))
        self.stdout.write(f'  Mode:           {"DEMO (synthetic + real)" if demo_mode else "REAL DATA ONLY"}')
        self.stdout.write(f'  Clear existing: {clear_existing}')
        self.stdout.write(f'  Lookback:       {days} days')
        if demo_mode:
            self.stdout.write(f'  Demo cities:    {", ".join(c[0].split()[0] for c in DEMO_CITIES)}')
        self.stdout.write('')

        try:
            zones = generate_zones(
                demo_mode=demo_mode,
                clear_existing=clear_existing,
                days=days,
            )

            if zones:
                self.stdout.write(self.style.SUCCESS(
                    f'\n✓ {len(zones)} delivery zone(s) created:\n'
                ))
                for z in zones:
                    self.stdout.write(self.style.SUCCESS(
                        f'  ID={z.pk:3}  {z.name}'
                    ))
                self.stdout.write('')
                self.stdout.write(self.style.HTTP_INFO(
                    'Verify in admin: http://localhost:8000/admin/Truck/deliveryzone/'
                ))
                self.stdout.write(self.style.HTTP_INFO(
                    'Run GPS replay to test geofence detection:'
                ))
                self.stdout.write(
                    '  python gps_replay.py --route atlanta_marietta --speed 2 '
                    '--pause-at 120 --username Joseph --password Jossey@2003 '
                    '--job-id c3023809-2838-47fd-ac08-02d19b5acd82'
                )
            else:
                self.stdout.write(self.style.WARNING(
                    '\n⚠ No zones created. Try running with --demo flag.'
                ))

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'\n✗ Zone generation failed: {exc}'))
            raise