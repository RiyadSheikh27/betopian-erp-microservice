import logging

from celery import shared_task

logger = logging.getLogger("apps.story")


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_story_thumbnail_task(self, story_id):
    from apps.story.models import Story
    from apps.utils.media import save_thumbnail_from_video_file

    try:
        story = Story.objects.get(pk=story_id)
    except Story.DoesNotExist:
        return

    if story.media_type != Story.MediaType.VIDEO or story.thumbnail:
        return

    try:
        save_thumbnail_from_video_file(story.file, story.thumbnail)
        story.save(update_fields=["thumbnail", "updated_at"])
        logger.info("Story thumbnail created | story_id=%s", story_id)
    except Exception as exc:
        logger.error("Story thumbnail failed | story_id=%s error=%s", story_id, exc)
        raise self.retry(exc=exc) from exc
