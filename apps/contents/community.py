import logging
import re

logger = logging.getLogger("apps.contents")

COMMUNITY_PROFILE_FIELDS = frozenset({"location", "company", "department"})


def community_assignment_profile(profile=None, user=None):
    """Build the profile dict used by assign_communities."""
    if profile is not None:
        return {
            "address": profile.get("address", ""),
            "company": profile.get("company", "") or profile.get("company_name", ""),
            "department": profile.get("department", ""),
        }
    if user is not None:
        return {
            "address": user.location or "",
            "company": user.company or "",
            "department": user.department or "",
        }
    return {"address": "", "company": "", "department": ""}


def should_enqueue_community_assignment(user, created, changed_fields):
    if created:
        return True
    if COMMUNITY_PROFILE_FIELDS & changed_fields:
        return True
    return not user.community_memberships.exists()


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
    from apps.chat.models import Conversation

    conv, _ = Conversation.objects.get_or_create(
        community=community,
        defaults={"type": "group"},
    )
    return conv


def sync_community_chat_member(community, user):
    from apps.chat.models import ConversationParticipant

    conv = ensure_community_conversation(community)
    ConversationParticipant.objects.get_or_create(conversation=conv, user=user)


def _community_keywords(community):
    keywords = community.keywords or []
    if keywords:
        return keywords
    if community.name:
        return [community.name]
    return []


def assign_communities(user, profile):
    """
    Add the user to matching communities they are not already in.
    Returns the number of new memberships created.
    """
    from apps.contents.models import Community, CommunityMember

    active_communities = Community.objects.filter(is_active=True)
    if not active_communities.exists():
        return 0

    address = profile.get("address", "")
    company = profile.get("company", "")
    department = profile.get("department", "")

    matched_ids = []
    for community in active_communities:
        keywords = _community_keywords(community)
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

    if not matched_ids:
        logger.debug(
            "No community match | user_id=%s company=%r department=%r address=%r",
            user.pk,
            company,
            department,
            address,
        )
        return 0

    existing_ids = set(
        CommunityMember.objects.filter(
            user=user, community_id__in=matched_ids
        ).values_list("community_id", flat=True)
    )
    new_ids = [cid for cid in matched_ids if cid not in existing_ids]
    if not new_ids:
        return 0

    CommunityMember.objects.bulk_create(
        [CommunityMember(community_id=cid, user=user) for cid in new_ids]
    )
    for cid in new_ids:
        sync_community_chat_member(Community.objects.get(pk=cid), user)

    logger.info(
        "Communities assigned | user_id=%s new=%s total_matched=%s",
        user.pk,
        len(new_ids),
        len(matched_ids),
    )
    return len(new_ids)
