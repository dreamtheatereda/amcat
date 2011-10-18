###########################################################################
#          (C) Vrije Universiteit, Amsterdam (the Netherlands)            #
#                                                                         #
# This file is part of AmCAT - The Amsterdam Content Analysis Toolkit     #
#                                                                         #
# AmCAT is free software: you can redistribute it and/or modify it under  #
# the terms of the GNU Affero General Public License as published by the  #
# Free Software Foundation, either version 3 of the License, or (at your  #
# option) any later version.                                              #
#                                                                         #
# AmCAT is distributed in the hope that it will be useful, but WITHOUT    #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or   #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public     #
# License for more details.                                               #
#                                                                         #
# You should have received a copy of the GNU Affero General Public        #
# License along with AmCAT.  If not, see <http://www.gnu.org/licenses/>.  #
###########################################################################

"""ORM Module representing users"""

from __future__ import print_function, absolute_import
import logging; log = logging.getLogger(__name__)

from amcat.tools import toolkit
from amcat.model.language import Language
from amcat.model.project import Project
from amcat.model import authorisation as auth

from django.contrib.auth.models import get_hexdigest, check_password
from django.core.exceptions import ValidationError
from django.db import models, DEFAULT_DB_ALIAS

from amcat.tools.model import AmcatModel

from amcat.db import dbtoolkit


class Affiliation(AmcatModel):
    id = models.AutoField(primary_key=True, db_column='affiliation_id')
    name = models.CharField(max_length=200)
    
    def __unicode__(self):
        return self.name

    class Meta():
        db_table = 'affiliations'   
        ordering = ['name']

    def can_update(self, user):
        return user.haspriv('manage_users')

class User(AmcatModel):
    id = models.AutoField(primary_key=True, db_column='user_id', editable=False)

    username = models.SlugField(max_length=50, unique=True, editable=False,
                                help_text="Only letters, digits and underscores are allowed.",
                                db_index=True)

    fullname = models.CharField(max_length=100, verbose_name="Full name")
    active = models.BooleanField(default=True)
    email = models.EmailField(max_length=100, unique=True)

    affiliation = models.ForeignKey(Affiliation)
    language = models.ForeignKey(Language, default=1)
    role = models.ForeignKey(auth.Role, null=False, default=0)

    def delete(self, **kwargs):
        self.active = False
        super(User, self).save(**kwargs)
    
    def __unicode__(self):
        return self.username

    class Meta():
        db_table = 'users'
        ordering = ['username']
    
    @property
    def projects(self):
        return Project.objects.filter(projectrole__user=self)

    ### Auth ###
    def can_read(self, user):
        return (user == self or
                user.haspriv('view_users') or
                (user.affiliation == self.affiliation and user.haspriv('view_users_same_affiliation')))

    def can_update(self, user):
        return (user == self or
                user.haspriv('manage_users') or
                (user.affiliation == self.affiliation and user.haspriv('manage_users_same_affiliation')))

    @classmethod
    def can_create(cls, user):
        return user.haspriv('manage_users')

    ### Mimic Django-functions ###
    def set_password(self, raw_password):
        if raw_password is None:
            self.active = False
        else:
            dbtoolkit.db.set_password(self.username, raw_password)

    def check_password(self, raw_password):
        return dbtoolkit.get_database().check_password(self, raw_password)

    def is_authenticated(self):
        return True if hasattr(self, 'db') else False

    def has_perm(self, perm):
        return self.haspriv(perm)

    def haspriv(self, privilege, onproject=None):
        """
        @type privilege: Privilege object, id, or str
        @param privilege: The requested privilege
        @param onproject: The project the privilege is requested on,
          or None (ignored) for global privileges
        
        @return: True or False
        """
        try: auth.check(self, privilege, onproject)
        except auth.AccessDenied:
            return False    
        return True

    @property
    def is_superuser(self):
        return (self.role.id == auth.ADMIN_ROLE)

    @classmethod
    def create_user(cls, username, fullname, password, email, affiliation, language, using=DEFAULT_DB_ALIAS, force=False):
        """
        @param force: force creation of user (i.e., ignore UserAlreadyExists exception raised by
        dbtoolkit. Might be useful for unittests.

        @type force: boolean
        """
        u = User()

        u.username = username
        u.email = email
        u.affiliation = affiliation
        u.language = language
        u.fullname = fullname

        if not (isinstance(password, basestring) and len(password) > 0):
            raise ValidationError("Please provide a valid password.")

        # Raise errors when invalid data is submitted
        u.full_clean()

        # Create database user
        try:
            dbtoolkit.get_database(using=using).create_user(username, password)
        except dbtoolkit.UserAlreadyExists as e:
            if not force: raise e

        # Create Django user
        u.save()

        return u
