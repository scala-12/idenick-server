"""request and response utils"""
from typing import Any, Optional, Union

from rest_framework import status
from rest_framework.response import Response


def get_request_param(request, name: str, is_int: bool = False, default: Union[str, int] = None,
                      base_filter: bool = False) -> Optional[Union[str, int]]:
    """return request param by name"""
    param = request.GET.get(('_' if base_filter else '') + name, default)

    result = None
    if param is not None:
        if param != '':
            if is_int:
                try:
                    result = int(param)
                except ValueError:
                    pass
            else:
                result = param
    elif not base_filter:
        result = get_request_param(
            request, name, is_int=is_int, default=default, base_filter=True)

    return result


def response(data: Any, status_value: int = status.HTTP_200_OK) -> Response:
    """response date with status with headers"""
    return Response(
        data,
        headers={'Access-Control-Allow-Origin': '*',
                 'Content-Type': 'application/json'},
        status=status_value)
