from django.apps import apps
from django.db.models import FileField
from django.db.models.signals import pre_delete, pre_save


def _file_fields(model):
    for field in model._meta.concrete_fields:
        if isinstance(field, FileField):
            yield field


def _delete_file(instance, field_name):
    file = getattr(instance, field_name, None)
    if file:
        file.delete(save=False)


def delete_model_files(sender, instance, **kwargs):
    for field in _file_fields(sender):
        _delete_file(instance, field.name)


def delete_replaced_files(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for field in _file_fields(sender):
        old_file = getattr(previous, field.name)
        new_file = getattr(instance, field.name)
        old_name = old_file.name if old_file else ""
        new_name = new_file.name if new_file else ""
        if old_name and old_name != new_name:
            old_file.delete(save=False)


def connect_media_cleanup_signals():
    for model in apps.get_models():
        if not any(_file_fields(model)):
            continue
        label = model._meta.label
        pre_delete.connect(
            delete_model_files,
            sender=model,
            dispatch_uid=f"media_cleanup_delete_{label}",
        )
        pre_save.connect(
            delete_replaced_files,
            sender=model,
            dispatch_uid=f"media_cleanup_replace_{label}",
        )
