from amcat.tools.model import AmcatModel

from django.db import models

class Language(AmcatModel):    
    id = models.IntegerField(primary_key=True, db_column="language_id")
    label = models.CharField(max_length=200)

    def __unicode__(self):
        return self.label

    class Meta():
        db_table = 'languages'
        app_label = 'model'
