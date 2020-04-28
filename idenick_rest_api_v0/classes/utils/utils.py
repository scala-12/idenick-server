"""report utils"""
from idenick_app.models import Organization
from idenick_rest_api_v0.serializers import organization_serializers


def get_objects_by_id(serializer, queryset=None, ids=None, clazz=None):
    """map objects to map {id: object}"""
    if (clazz is not None) and (ids is not None):
        queryset = clazz.objects.filter(id__in=ids)
    result = None
    if queryset is not None:
        data = map(lambda i: serializer(i).data, queryset)
        result = {}
        for o in data:
            result.update({o.get('id'): o})

    return result


def get_organizations_by_id(ids):
    """map organization to map {id: organization}"""
    return get_objects_by_id(organization_serializers.ModelSerializer, clazz=Organization, ids=ids)
