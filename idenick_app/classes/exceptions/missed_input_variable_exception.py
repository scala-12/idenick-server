"""missed input variable in method"""
from typing import Optional

from idenick_app.classes.exceptions.abstract_exception import Error


class MissedInputVariableException(Error):
    """missed input variable in method"""

    def __init__(self, message: Optional[str] = 'Missed variable'):
        self.message = message
