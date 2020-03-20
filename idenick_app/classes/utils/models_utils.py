"""models"""

from idenick_app.models import AbstractEntry
from django.db.models import fields

DELETED_STATUS = 'удален'


def get_related_entities_count(Relation_class: AbstractEntry,
                               relation_filter: dict,
                               Object_class: AbstractEntry,
                               relation_field: str):
    relation_filter.update(dropped_at=None)
    ids = Relation_class.objects.filter(
        **relation_filter).values_list(relation_field, flat=True)

    return Object_class.objects.filter(id__in=ids, dropped_at=None).count()

class TinyIntegerField(fields.SmallIntegerField):
    def db_type(self, connection):
        return "tinyint"

    def get_internal_type(self):
        return "SmallIntegerField"

    def to_python(self, value):
        if value is None:
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            raise exceptions.ValidationError(
                _("This value must be a short integer."))
