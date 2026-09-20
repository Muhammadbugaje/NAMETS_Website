"""
Safe loaddata: skips rows that already exist, disconnects signals.
Usage: python loaddata_safe.py local_backup.json
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'namets.settings')
django.setup()

from django.core import serializers
from django.db import transaction, IntegrityError
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete

fixture = sys.argv[1] if len(sys.argv) > 1 else 'local_backup.json'

# 1. Disconnect signals
saved_signals = {}
count = 0
for sig in (post_save, pre_save, post_delete, pre_delete):
    saved_signals[sig] = sig.receivers[:]
    count += len(sig.receivers)
    sig.receivers = []
print(f"Disconnected {count} signal receiver(s).")

# 2. Load, skipping duplicates
loaded = skipped = failed = 0
errors = []

try:
    with open(fixture, 'r', encoding='utf-8') as f:
        data = f.read()

    for obj in serializers.deserialize('json', data, handle_forward_references=True):
        try:
            with transaction.atomic():
                obj.save()
            loaded += 1
            if loaded % 25 == 0:
                print(f"  ... {loaded} loaded, {skipped} skipped", flush=True)
        except IntegrityError as e:
            skipped += 1
        except Exception as e:
            failed += 1
            errors.append(f"{obj.object.__class__.__name__} pk={obj.object.pk}: {e}")

finally:
    for sig, receivers in saved_signals.items():
        sig.receivers = receivers
    print("Signals restored.")

print()
print(f"Loaded:  {loaded}")
print(f"Skipped: {skipped} (already existed)")
print(f"Failed:  {failed}")

if errors:
    print("\nFirst 10 errors:")
    for err in errors[:10]:
        print(f"  {err}")