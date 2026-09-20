from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Reset all PostgreSQL sequences to MAX(id) + 1 after a loaddata."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                  quote_ident(table_namespace.nspname) || '.' || quote_ident(class_.relname) AS table_name,
                  quote_ident(sequence_namespace.nspname) || '.' || quote_ident(class_sequence.relname) AS sequence_name,
                  quote_ident(pg_attribute.attname) AS column_name
                FROM pg_class AS class_
                JOIN pg_namespace AS table_namespace ON table_namespace.oid = class_.relnamespace
                JOIN pg_attribute ON pg_attribute.attrelid = class_.oid AND pg_attribute.attnum > 0
                JOIN pg_class AS class_sequence ON class_sequence.oid = pg_attribute.attrelid
                JOIN pg_namespace AS sequence_namespace ON sequence_namespace.oid = class_sequence.relnamespace
                WHERE table_namespace.nspname = 'public'
                  AND class_.relkind = 'r'
                  AND class_sequence.relkind = 'S'
                  AND pg_attribute.attname = 'id'
            """)
            rows = cursor.fetchall()

            for table, sequence, column in rows:
                cursor.execute(
                    f"SELECT setval('{sequence}', "
                    f"COALESCE((SELECT MAX({column}) FROM {table}), 1) + 1, false)"
                )
                self.stdout.write(f"✅ {table} → {sequence}")

        self.stdout.write(self.style.SUCCESS(f"Fixed {len(rows)} sequence(s)."))