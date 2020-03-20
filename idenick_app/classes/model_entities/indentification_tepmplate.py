"""Employee templates model"""
from django.db import models

from idenick_app.classes.constants.identification import algorithm_constants
from idenick_app.classes.utils.models_utils import TinyIntegerField


class IndentificationTepmplate(models.Model):
    """Employee templates model"""
    id = models.AutoField(primary_key=True,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, db_index=True,)
    algorithm_type = models.SmallIntegerField(
        db_column='algorithm', choices=algorithm_constants.ALGORITHM_TYPE, db_index=True,)
    algorithm_version = TinyIntegerField(
        db_column='algorithmVersion',)
    template = models.BinaryField()
    quality = TinyIntegerField(
        null=True, blank=True, default=0,)
    config = models.CharField(
        max_length=2000, null=True, blank=True,)
    created_at = models.DateTimeField(
        db_column='rcreated', auto_now_add=True,)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True, db_index=True,)

    def __str__(self):
        return '{ id: %s, employee: %s, algorithm_type: %s, algorithm_version: %s, quality: %s,' \
            + ' config: %s, created_at: %s, dropped_at: %s, }' % (self.id,
                                                                  self.employee,
                                                                  self.algorithm_type,
                                                                  self.algorithm_version,
                                                                  self.quality,
                                                                  self.config,
                                                                  self.created_at,
                                                                  self.dropped_at,)

    class Meta:
        db_table = 'templates'
