from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from django.urls import reverse
from .models import Notification, ActivityLog


def get_group_members(group_name):
    try:
        return Group.objects.get(name=group_name).user_set.filter(is_active=True, is_staff=True)
    except Group.DoesNotExist:
        return User.objects.none()


def notify_group(group_name, ntype, title, message, link=""):
    recipients = set(get_group_members(group_name)) | set(User.objects.filter(is_superuser=True, is_active=True))
    for user in recipients:
        Notification.objects.create(
            recipient=user, notification_type=ntype,
            title=title, message=message, admin_link=link,
        )


def log_action(action, model_name, object_repr, link=""):
    ActivityLog.objects.create(action=action, model_name=model_name, object_repr=str(object_repr)[:300], admin_link=link)


def connect_signals():
    from communications.models import Announcement
    from events.models import Event
    from community.models import MembershipApplication, TutorApplication, Question
    from academics.models import IslamiyyaRegistration, UserResourceSubmission
    from lostfound.models import Item
    from gallery.models import Gallery

    # ── Announcements ──────────────────────────────────────────
    @receiver(post_save, sender=Announcement, weak=False)
    def on_announcement(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:communications_announcement_change", args=[instance.pk])
        except: link = ""
        notify_group("Communications Team", Notification.Type.ANNOUNCEMENT,
            f"New announcement: {instance.title}", f"Category: {getattr(instance,'category','General')}", link)
        log_action("created", "Announcement", instance.title, link)

    # ── Events ─────────────────────────────────────────────────
    @receiver(post_save, sender=Event, weak=False)
    def on_event(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:events_event_change", args=[instance.pk])
        except: link = ""
        notify_group("Events Team", Notification.Type.EVENT,
            f"New event: {instance.title}", f"Scheduled: {getattr(instance,'date','TBD')}", link)
        log_action("created", "Event", instance.title, link)

    # ── Membership Applications ────────────────────────────────
    @receiver(post_save, sender=MembershipApplication, weak=False)
    def on_membership(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:community_membershipapplication_change", args=[instance.pk])
        except: link = ""
        notify_group("Community Team", Notification.Type.MEMBERSHIP,
            f"New membership application: {getattr(instance,'name','Unknown')}",
            f"Email: {getattr(instance,'email','')}", link)
        log_action("created", "Membership Application", getattr(instance, 'name', str(instance)), link)

    # ── Tutor Applications ─────────────────────────────────────
    @receiver(post_save, sender=TutorApplication, weak=False)
    def on_tutor_app(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:community_tutorapplication_change", args=[instance.pk])
        except: link = ""
        notify_group("Community Team", Notification.Type.TUTOR_APP,
            f"New tutor application: {getattr(instance,'name','Unknown')}", "Review in admin panel.", link)
        log_action("created", "Tutor Application", getattr(instance, 'name', str(instance)), link)

    # ── Islamiyyah Registrations ───────────────────────────────
    @receiver(post_save, sender=IslamiyyaRegistration, weak=False)
    def on_islamiyya(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:academics_islamiyyaregistration_change", args=[instance.pk])
        except: link = ""
        notify_group("Academics Team", Notification.Type.ISLAMIYYA,
            f"New Islamiyyah registration: {getattr(instance,'name','Unknown')}",
            f"Level: {getattr(instance,'level','N/A')}. Awaiting verification.", link)
        log_action("created", "Islamiyyah Registration", getattr(instance, 'name', str(instance)), link)

    # ── Lost & Found ───────────────────────────────────────────
    @receiver(post_save, sender=Item, weak=False)
    def on_lostfound(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:lostfound_item_change", args=[instance.pk])
        except: link = ""
        notify_group("Gallery Team", Notification.Type.LOST_FOUND,
            f"New lost & found item: {getattr(instance,'name',str(instance))}",
            str(getattr(instance,'description',''))[:120], link)
        log_action("created", "Lost & Found", getattr(instance, 'name', str(instance)), link)

    # ── Q&A ────────────────────────────────────────────────────
    @receiver(post_save, sender=Question, weak=False)
    def on_question(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:community_question_change", args=[instance.pk])
        except: link = ""
        notify_group("Community Team", Notification.Type.QA,
            "New Q&A question submitted",
            str(getattr(instance,'question_text', str(instance)))[:200], link)
        log_action("created", "Q&A Question", str(instance)[:100], link)

    # ── Gallery ────────────────────────────────────────────────
    @receiver(post_save, sender=Gallery, weak=False)
    def on_gallery(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:gallery_gallery_change", args=[instance.pk])
        except: link = ""
        notify_group("Gallery Team", Notification.Type.GALLERY,
            f"New gallery album: {getattr(instance,'title','Untitled')}",
            f"Date: {getattr(instance,'date','N/A')}", link)
        log_action("created", "Gallery", getattr(instance, 'title', str(instance)), link)
        
        
    @receiver(post_save, sender=UserResourceSubmission, weak=False)
    def on_resource_submission(sender, instance, created, **kwargs):
        if not created:
            return
        try: link = reverse("admin:academics_userresourcesubmission_change", args=[instance.pk])
        except: link = ""
        notify_group(
            "Academics Team",
            Notification.Type.GENERAL,
            f"New resource submission: {instance.title}",
            f"Submitted by {instance.submitted_by} ({instance.email}). {instance.description[:100] if instance.description else ''}",
            link
        )
        log_action("created", "Resource Submission", instance.title, link)