"""Employee templates model. READ ONLY"""
from django.db import models

from idenick_app.classes.constants.identification import algorithm_constants


class IndentificationTepmplate(models.Model):
    """Employee templates model. READ ONLY"""
    id = models.AutoField(primary_key=True, editable=False,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, editable=False, db_index=True,)
    algorithm_type = models.IntegerField(
        db_column='algorithm', choices=algorithm_constants.ALGORITHM_TYPE, editable=False, db_index=True,)
    algorithm_version = models.SmallIntegerField(
        db_column='algorithmVersion', editable=False,)
    template = models.BinaryField(max_length=8000, editable=False,)
    quality = models.SmallIntegerField(editable=False, null=True, blank=True,)
    config = models.CharField(
        max_length=2000, editable=False, null=True, blank=True,)
    created_at = models.DateTimeField(
        db_column='rcreated', auto_now_add=True, editable=False,)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True, editable=False, db_index=True,)

    class Meta:
        db_table = 'templates'
