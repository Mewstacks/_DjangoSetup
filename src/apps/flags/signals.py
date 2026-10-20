from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.flags.models import Flag, FlagRule, Setting
from apps.flags.services import invalidate


@receiver([post_save, post_delete], sender=Flag)
@receiver([post_save, post_delete], sender=FlagRule)
@receiver([post_save, post_delete], sender=Setting)
def _invalidate(sender: object, **kwargs: object) -> None:
    invalidate()
