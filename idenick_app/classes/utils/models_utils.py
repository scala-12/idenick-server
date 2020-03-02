"""models"""

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry

DELETED_STATUS = 'удален'


def get_related_entities_count(Relation_class: AbstractEntry,
                               relation_filter: dict,
                               Object_class: AbstractEntry,
                               relation_field: str):
    relation_filter.update(dropped_at=None)
    ids = Relation_class.objects.filter(
        **relation_filter).values_list(relation_field, flat=True)

    return Object_class.objects.filter(id__in=ids, dropped_at=None).count()
