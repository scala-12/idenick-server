"""login utils"""
from functools import wraps
from typing import Optional

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from idenick_app.classes.model_entities.login import Login
from idenick_rest_api_v0.classes.utils import request_utils


def login_check_decorator(*roles):
    """access to method if has role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            args_list = list(args)
            request = None
            if isinstance(args_list[0], Request):
                request = args_list[0]
            elif isinstance(args_list[1], Request):
                request = args_list[1]

            result = None
            if _check_role(request, roles):
                result = view_func(*args, **kwargs)
            else:
                result = _login_error_response()

            return result

        return wrapped

    return decorator


def _login_error_response() -> Response:
    return request_utils.response({'redirect2Login': True},
                                  status_value=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _check_role(request, roles) -> bool:
    has_role = False
    if request.user.is_authenticated:
        login = get_login(request.user)
        if login is not None:
            roles_list = list(roles)
            if roles_list:
                i = 0
                while ((i < len(roles_list)) and not(has_role)):
                    if roles_list[i] == login.role:
                        has_role = True
                    else:
                        i += 1
            else:
                # available for all roles
                has_role = True
    return has_role


def get_login(user: User) -> Optional[Login]:
    """return user login"""
    result = None
    if user.is_authenticated:
        login = Login.objects.filter(user=user)
        if login.exists():
            result = login.first()

    return result


def has_login_check(user: User) -> bool:
    """check user login is exists"""
    login = get_login(user)
    return login is not None
