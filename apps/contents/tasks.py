import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger("apps.contents")


@shared_task
def assign_communities_task(user_id, profile):
    from apps.contents.community import assign_communities

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "Community assign skipped — user not found | user_id=%s", user_id
        )
        return

    added = assign_communities(user, profile)
    if added:
        logger.info(
            "Community assign task completed | user_id=%s added=%s", user_id, added
        )


def enqueue_community_assignment(user, profile=None, *, created=False, changed_fields=None):
    """Schedule async community assignment when profile data may affect membership."""
    from apps.contents.community import (
        community_assignment_profile,
        should_enqueue_community_assignment,
    )

    changed = set(changed_fields or ())
    if not should_enqueue_community_assignment(user, created, changed):
        return

    profile_data = community_assignment_profile(profile=profile, user=user)
    try:
        assign_communities_task.delay(str(user.pk), profile_data)
        logger.debug("Community assign queued | user_id=%s", user.pk)
    except Exception as exc:
        logger.error(
            "Community assign queue failed | user_id=%s error=%s", user.pk, exc
        )
