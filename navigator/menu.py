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

"""
This module contains all logic which is needed to render all menu's within
the navigator. Since 3.2 it is really simplified, and hopefully well-
documented.
"""

from collections import OrderedDict
from itertools import chain

from amcat.models import Role, Privilege, Privilege
from amcat.models.authorisation import check

from django.core.urlresolvers import reverse, resolve, reverse_lazy
from django.views.generic.base import TemplateView

import logging; log = logging.getLogger(__name__)

PROJECT_ID = "project_id"

### VIEWS ###
class MenuView(TemplateView):
    def get_context_data(self, **kwargs):
        ctx = super(MenuView, self).get_context_data(**kwargs)
        ctx.update({"menu":tuple(generate_menu(self.request))})
        return ctx


### GENERIC NAVIGATOR_MENU ITEMS ###
class MenuItem(object):
    """
    A MenuItem represents an item in a menu (what's in a name?). It takes options
    which determine whether it is visible, under specific circumstances.
    """
    def __init__(self, label, url=None, privilege=None, role=None):
        self.label = label
        self.url = url
        self.privilege = privilege
        self.role = role

    def __repr__(self):
        return "<MenuItem: {label}>".format(**self.__dict__)        

    def _check_privilege(self, user, project):
        return user.haspriv(self.privilege, project) if self.privilege else True

    def _check_role(self, user):
        return True

    def is_visible(self, user=None, project=None):
        """Checks whether this item is visible for logged in user."""
        return self._check_privilege(user, project) and self._check_role(user)

    def is_selected(self, request):
        """
        Returns True if, based on the current request, this menu-item is
        selected.
        """
        url = self.get_url(request)
        cur_url = request.META["PATH_INFO"]

        if url == cur_url:
            return True
            
        if url is None:
            return False

        # We add a forward slash to prevent collisions with 'wrong' urls.
        url = url if url.endswith("/") else "{}/".format(url)
        return cur_url.startswith(url)

    def get_url(self, request=None):
        # Try to reverse given url, if it does not look like an url
        if isinstance(self.url, basestring) and self.url.find("/") == -1:
            return reverse(self.url)

        return self.url

    def to_dict(self, request, project=None):
        """Converts this item in to a dictionary, based on current request"""
        path_kwargs = resolve(request.META["PATH_INFO"]).kwargs
        if PROJECT_ID in path_kwargs.keys():
            project = Project.objects.get(id=path_kwargs[PROJECT_ID])

        return {
            "label" : self.label,
            "is_selected" : self.is_selected(request),
            "is_visible" : self.is_visible(request.user, project),
            "url" : self.get_url(request)
        }

class MenuReverseItem(MenuItem):
    """
    This is a menu-item which needs parameters present in the url to resolve its
    destination. It takes the same arguments a MenuItem, but the url-arugment needs
    to be generated using reverse_with().
    """
    def get_url(self, request):
        # We don't need to concern ourselves with how MenuItem stores the given url
        url = super(MenuReverseItem, self).get_url(request)

        # To resolve reverse_with urls, we neeed the kwargs of the currently
        # requested url.
        path_kwargs = resolve(request.META["PATH_INFO"]).kwargs
        path_keys = set(path_kwargs.keys())

        if isinstance(url, tuple):
            # This is a reverse_with url
            view, args, kwargs = url

            if (set(args) - path_keys):
                # There are arguments which are requested for this menu item
                # to resolve, which are not in the url.
                log.debug("Could not resolve {url} with only {path_keys} available".format(**locals()))
                return

            # We can resolve it!
            kwargs.update({ a : path_kwargs.get(a) for a in args})
            return reverse(view, kwargs=kwargs)

        # We don't know this type, probably just a string (URL)
        return url

### SPECIFIC NAVIGATOR_MENU ITEMS ###
class MyDetails(MenuItem):
    def __init__(self, label):
        super(MenuItem, self).__init__(label)

    def is_selected(self, request):
        user_id = resolve(request.META["PATH_INFO"]).kwargs.get("user_id", None)
        return user_id == request.user.id

    def get_url(self, request):
        return reverse("user", kwargs=dict(user_id=request.user.id))
    
### TOOLS ###
def generate_menu(request):
    """
    This function returns an iterator which yields tuples with dictionaries, with
    the latter representing menu-items. As the main menu is always visible, the 
    first tuple yielded will be formatted like:

     { category1 : (item1, item2),
       category2 : ... }

    instead of the usual:

     (item1, item2)

    Each item is a dictionary with the keys: is_selected, is_visible and url.
    """
    yield OrderedDict(_generate_main_menu(request))

    # Finding selected menu item..
    items = _get_children_selected(request, chain(*NAVIGATOR_MENU.values()))
    for submenu in _generate_submenus(request, items):
        yield submenu

def _get_children_selected(request, submenu):
    for item, children in submenu:
        if item.is_selected(request):
            return children
    
def _generate_main_menu(request):
    for cat, items in NAVIGATOR_MENU.items():
        yield (cat.label, tuple(item.to_dict(request) for (item, children) in items))

def _generate_submenus(request, items=None):
    if items is None:
        return ()

    return ((tuple(item.to_dict(request) for item in items),) 
        + _generate_submenus(request, _get_children_selected(request, items)))

def reverse_with(view, *args, **kwargs):
    """
    An url will be generated using django's reverse() with the provided kwargs
    and the "filled" args. So, when "project_id" is passed as an (non-keyword)
    argument it is filled using the arguments provided in the current requests
    url.
    """
    return (view, args, kwargs)

### DEFINITION ###
PROJECTS_MENU = (

)

USERS_MENU = (
    (MenuItem("Active affiliated users", "affiliated-users"), None),
    (MenuItem("All affiliated users", "all-affiliated-users"), None),
    (MenuItem("All users", "all-users", privilege=(
        Privilege.objects.get(label="view_users", role__projectlevel=False)
    )), None),
)

PLUGINS_MENU = (

)

CODINGJOBS_MENU = (

)

NAVIGATOR_MENU = OrderedDict((
    # Categories
    (MenuItem(None), (
        (MenuItem("Projects", "projects"), PROJECTS_MENU),
        (MenuItem("My codingjobs", "my-codingjobs"), CODINGJOBS_MENU)
    )),
    (MenuItem("Lists"), (
        (MenuItem("Users", "users"), USERS_MENU),
        (MenuItem("Media", "media"), None),
        (MenuItem("Plugins", "plugins"), PLUGINS_MENU),
        (MenuItem("Scrapers", "scrapers"), None),
    )),
    (MenuItem("User"), (
        (MenuItem("My details", "self"), None),
        (MenuItem("Logout", "accounts-logout"), None),
    )),
    (MenuItem("Developer", role=Role.objects.get(label="developer")), (
        (MenuItem("API", "api"), None),
        (MenuItem("Code", "https://code.google.com/p/amcat/"), None),
        (MenuItem("Logs", "/sentry/"), None),
    )),
))

