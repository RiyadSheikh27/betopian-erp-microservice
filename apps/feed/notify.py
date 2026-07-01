import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("apps.feed")

_MESSAGES = {
    "posts": "New post, please refresh.",
    "reels": "New reel, please refresh.",
    "community": "New post, please refresh.",
}


def _broadcast(group, feed, *, exclude_user_id=None, community_id=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    payload = {
        "type": "feed_update",
        "feed": feed,
        "community_id": str(community_id) if community_id else None,
        "message": _MESSAGES[feed],
    }
    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "feed_update",
            "exclude_user_id": str(exclude_user_id) if exclude_user_id else None,
            "payload": payload,
        },
    )
    logger.debug("Feed notify | group=%s feed=%s", group, feed)


def notify_post_created(post, author_id):
    from apps.contents.models import Post, PostMedia

    if post.privacy != Post.Privacy.PUBLIC:
        return

    if post.community_id:
        _broadcast(
            f"feed_community_{post.community_id}",
            "community",
            exclude_user_id=author_id,
            community_id=post.community_id,
        )

    _broadcast(
        "feed_posts",
        "posts",
        exclude_user_id=author_id,
        community_id=post.community_id,
    )

    if post.media.filter(media_type=PostMedia.MediaType.VIDEO).exists():
        _broadcast("feed_reels", "reels", exclude_user_id=author_id)


def notify_reel_created(reel, author_id):
    from apps.contents.models import Reel

    if reel.privacy != Reel.Privacy.PUBLIC:
        return
    _broadcast("feed_reels", "reels", exclude_user_id=author_id)
