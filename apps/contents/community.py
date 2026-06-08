import logging
import re
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("apps.contents")

REASSIGNMENT_DAYS = 7  # Number of days after which to reassign communities

""" Helper functions for community assignment """


def _should_assign(user):
    if user is None:
        return False
    if user.community_assigned_at is None:
        return True
    return timezone.now() - user.community_assigned_at > timedelta(
        days=REASSIGNMENT_DAYS
    )


def _normalize(text):
    if not text:
        return set()
    text = text.lower()

    text = re.sub(r"[^\w\s]", " ", text)
    return set(text.split())


def _matches(profile_text, keywords):
    if not profile_text:
        return False

    normalized_text = profile_text.lower()
    normalized_tokens = _normalize(profile_text)

    for kw in keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        if kw_lower in normalized_text:
            return True
        if kw_lower in normalized_tokens:
            return True
    return False

def ensure_community_conversation(community):
    from apps.chat.models import Conversation, ConversationParticipant
    conv, _ = Conversation.objects.get_or_create(
        community=community,
        defaults={"type": "group"},
    )
    return conv

def sync_community_chat_member(community, user):
    from apps.chat.models import ConversationParticipant
    conv = ensure_community_conversation(community)
    ConversationParticipant.objects.get_or_create(conversation=conv, user=user)

""" 
Main function to assign communities based on central profile data. 
Called from authentication backend after user sync. 
"""


def assign_communities(user, profile):
    if not _should_assign(user):
        return

    # Imported here to avoid circular imports at module load time
    from apps.contents.models import Community, CommunityMember

    active_communities = Community.objects.filter(is_active=True)
    if not active_communities.exists():
        user.community_assigned_at = timezone.now()
        user.save(update_fields=["community_assigned_at"])
        return

    # Pull relevant fields from central profile
    address = profile.get("address", "")
    company = profile.get("company", "")
    department = profile.get("department", "")

    # Match each community against the corresponding profile field
    matched_ids = []
    for community in active_communities:
        keywords = community.keywords or []
        if not keywords:
            continue

        if community.type == Community.CommunityType.LOCATION:
            if _matches(address, keywords):
                matched_ids.append(community.id)

        elif community.type == Community.CommunityType.COMPANY:
            if _matches(company, keywords):
                matched_ids.append(community.id)

        elif community.type == Community.CommunityType.DEPARTMENT:
            if _matches(department, keywords):
                matched_ids.append(community.id)

    if matched_ids:
        existing_ids = set(
            CommunityMember.objects.filter(
                user=user, community_id__in=matched_ids
            ).values_list("community_id", flat=True)
        )
        new_ids = [cid for cid in matched_ids if cid not in existing_ids]

        if new_ids:
            CommunityMember.objects.bulk_create(
                [CommunityMember(community_id=cid, user=user) for cid in new_ids]
            )
            # Sync user into community group chat
            for cid in new_ids:
                from apps.contents.models import Community as C
                sync_community_chat_member(C.objects.get(pk=cid), user)
            logger.info(
                "Communities assigned | user_id=%s new=%s total_matched=%s",
                user.pk, len(new_ids), len(matched_ids),
            )

    user.community_assigned_at = timezone.now()
    user.save(update_fields=["community_assigned_at"])
