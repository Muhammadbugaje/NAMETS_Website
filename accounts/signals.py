from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import OfficeAssignment


@receiver(post_save, sender=OfficeAssignment)
def sync_group_membership_on_assign(sender, instance, created, **kwargs):
    """Add user to linked_group when assigned to an office."""
    if instance.office.linked_group and instance.is_active:
        instance.user.groups.add(instance.office.linked_group)


@receiver(post_delete, sender=OfficeAssignment)
def sync_group_membership_on_remove(sender, instance, **kwargs):
    """Remove user from linked_group if no other active office links to it."""
    if instance.office.linked_group:
        still_linked = OfficeAssignment.objects.filter(
            user=instance.user,
            office__linked_group=instance.office.linked_group,
            is_active=True
        ).exclude(pk=instance.pk).exists()
        if not still_linked:
            instance.user.groups.remove(instance.office.linked_group)