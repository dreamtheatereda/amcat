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


from django import forms
from amcat.models import Project, ArticleSet, Medium, Codebook, Language, Label

import datetime, re

import logging
log = logging.getLogger(__name__)


class ModelMultipleChoiceFieldWithIdLabel(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return "%s - %s" % (obj.id, obj.name)
        
class ModelChoiceFieldWithIdLabel(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s - %s" % (obj.id, obj)
        
        
class DateIntervalForm(forms.Form):
    interval = forms.ChoiceField(
            choices=(
                ('day', 'Day'), 
                ('week', 'Week'), 
                ('month', 'Month'), 
                ('quarter', 'Quarter'), 
                ('year', 'Year')
            ), initial='month')
        
class InlineTableOutputForm(forms.Form):
    """Form with all the possible outputs for a table3 object"""
    output = forms.ChoiceField(choices=(
        ('csv', 'CSV (semicolon separated)'),
        ('comma-csv', 'CSV (comma separated)'),
        ('excel', 'Excel (.xslx)'),
        ('spss', 'SPSS (.sav)'), 
        ('json-html', 'Show in navigator')
     ), initial='json-html')
        
class TableOutputForm(forms.Form):
    """Form with all the possible outputs for a table3 object"""
    output = forms.ChoiceField(choices=(
        ('csv', 'CSV (semicolon separated)'),
        ('comma-csv', 'CSV (comma separated)'),
        ('excel', 'Excel (.xslx)'),
        ('spss', 'SPSS (.sav)'), 
        ('html', 'HTML')
     ), initial='csv')
        
        
class GeneralColumnsForm(forms.Form):
    """represents column for any object, as a string seperated with ,"""
    columns = forms.CharField()

    def clean_columns(self):
        data = self.cleaned_data['columns']
        data = [x.strip() for x in data.split(',') if x.strip()]
        return data
        
        
class ArticleColumnsForm(forms.Form):
    columns = forms.MultipleChoiceField( # columns are used to indicate which columns should be loaded from the database (for performance reasons)
            choices=(
                ('article_id', 'Article ID'),
                ('hits', 'Hits'),
                ('keywordInContext', 'Keyword in Context'),
                ('date','Date'),
                ('interval', 'Interval'),
                ('medium_id','Medium ID'),
                ('medium_name','Medium Name'),
                ('project_id','Project ID'),
                ('project_name','Project Name'),
                ('pagenr','Page number'),
                ('section','Section'),
                ('author','Author'),
                ('length','Length'),
                ('url','url'),
                ('parent_id','Parent Article ID'),
                ('externalid','External ID'),
                ('additionalMetadata','Additional Metadata'),
                ('headline','Headline'),
                ('byline','Byline'),
                ('text','Article Text')
            ), initial = ('article_id', 'date', 'medium_id', 'medium_name', 'headline')
    )
    columnInterval = forms.ChoiceField(
            choices=(
                ('day', 'Day'), 
                ('week', 'Week'), 
                ('month', 'Month'), 
                ('quarter', 'Quarter'), 
                ('year', 'Year')
            ), initial='month', label='Column Interval', required=False)

            
            
class SearchQuery(object):
    """
    represents a query object that contains both a (Solr) query and an optional label
    """
    def __init__(self, query, label=None):
        self.query = query
        self.declared_label = label
        self.label = label or query
            

DATETYPES = {
    "all" : "All Dates",
    "on" : "On",
    "before" : "Before",
    "after" : "After",
    "between" : "Between",
}
            
class SelectionForm(forms.Form):
    # TODO: change to projects of user
    projects = ModelMultipleChoiceFieldWithIdLabel(queryset=Project.objects.order_by('-pk')) 
    articlesets = ModelMultipleChoiceFieldWithIdLabel(queryset=ArticleSet.objects.none(), required=False)
    mediums = ModelMultipleChoiceFieldWithIdLabel(queryset=Medium.objects.none(), required=False)
    query = forms.CharField(widget=forms.Textarea, required=False)
    articleids = forms.CharField(widget=forms.Textarea, required=False)
    datetype = forms.ChoiceField(choices=DATETYPES.items(), initial='all')
    startDate = forms.DateField(input_formats=('%d-%m-%Y',), required=False)
    endDate = forms.DateField(input_formats=('%d-%m-%Y',), required=False)
    onDate = forms.DateField(input_formats=('%d-%m-%Y',), required=False)
    includeAll = forms.BooleanField(label="Include articles not matched by any keyword", required=False)
    codebook = ModelChoiceFieldWithIdLabel(queryset=Codebook.objects.all(), required=False, label="Use Codebook")
    codebooklanguage = ModelChoiceFieldWithIdLabel(queryset=Language.objects.all(), required=False, label="Language for keywords")
    # queries will be added by clean(), that contains a list of SearchQuery objects
    
    def __init__(self, data=None, *args, **kwargs):
        super(SelectionForm, self).__init__(data, *args, **kwargs)
        if data is None: return

        self.fields['mediums'].queryset = Medium.objects.all().order_by('pk')

        if hasattr(data, "getlist"):
            projectids = data.getlist("projects")
        else:
            projectids = data.get("projects")

        if isinstance(projectids, (list, tuple)):
            project = Project.objects.get(id=projectids[0])
        else:
            return

        self.fields['articlesets'].queryset = project.all_articlesets().order_by('-pk')

        self.fields['codebook'].queryset = Codebook.objects.filter(project_id=project.id)
        
    def clean(self):
        cleanedData = self.cleaned_data
        if cleanedData.get('datetype') in ('after', 'all') and 'endDate' in cleanedData:
            del cleanedData['endDate']
        if cleanedData.get('datetype') in ('before', 'all') and 'startDate' in cleanedData:
            del cleanedData['startDate']
        if cleanedData.get('datetype') == 'on':
            cleanedData['datetype'] = 'between'
            cleanedData['startDate'] = cleanedData['onDate'] 
            cleanedData['endDate'] = cleanedData['onDate'] + datetime.timedelta(1)

        missingDateMsg = "Missing date"
        if 'endDate' in cleanedData and cleanedData['endDate'] == None: # if datetype in (before, between)
            self._errors["endDate"] = self.error_class([missingDateMsg])
            del cleanedData['endDate']
            #raise forms.ValidationError("Missing end date")
        if 'startDate' in cleanedData and cleanedData['startDate'] == None: # if datetype in (after, between)
            self._errors["startDate"] = self.error_class([missingDateMsg])
            del cleanedData['startDate']
            #raise forms.ValidationError("Missing start date")
        if cleanedData.get('query') == '':
            del cleanedData['query']
            cleanedData['useSolr'] = False
        else:
            cleanedData['useSolr'] = True
            cleanedData['queries'] = []
            queries = [x.strip() for x in cleanedData['query'].split('\n') if x.strip()] # split lines
            for query in queries:
                if '#' in query:
                    label = query.split('#')[0]
                    if len(label) == 0 or len(label) > 20:
                        self._errors["query"] = self.error_class(['Invalid query label (before the #)'])
                    query = query.split('#')[1]
                    if len(query) == 0:
                        self._errors["query"] = self.error_class(['Invalid query (after the #)'])
                elif '\t' in query:
                    label = query.split('\t')[0]
                    if len(label) == 0 or len(label) > 20:
                        self._errors["query"] = self.error_class(['Invalid query label (before the tab)'])
                    query = query.split('\t')[1]
                    if len(query) == 0:
                        self._errors["query"] = self.error_class(['Invalid query (after the tab)'])
                else: 
                    label = None
                cleanedData['queries'].append(SearchQuery(query, label))


        if 'queries' in cleanedData:
            if cleanedData['includeAll']:
                cleanedData['queries'].insert(0, SearchQuery("*:*", "All"))
            cleanedData['queries'] = list(resolve_codes(cleanedData['queries'], cleanedData['codebook'], cleanedData['codebooklanguage']))

        try:
            cleanedData['articleids'] = [int(x.strip()) for x in cleanedData['articleids'].split('\n') if x.strip()]
        except:
            self._errors["articleids"] = self.error_class(['Invalid article ID list'])

            
        # if 'output' not in cleanedData:
            # cleanedData['output'] = 'json-html'
            
        return cleanedData

def resolve_codes(queries, codebook, keyword_language):
    if codebook and not keyword_language:
        raise Exception("Along with a codebook, you must also select a language.")

    # build label -> definition dictionary
    cb_lookup = {} # markup string -> keywords
    if codebook:
        labels = {} # code, language -> label
        for label in Label.objects.filter(code__codebook_codes__codebook=codebook):
            labels[label.code_id, label.language_id] = label.label

        for (code_id, language_id), label in labels.iteritems():
            if language_id == keyword_language.id:
                kw_label = labels[code_id, keyword_language.id]
                cb_lookup[u"{{{label}}}".format(**locals())] = u"({kw_label})".format(**locals())

    q_lookup = {u'{{query.declared_label}}'.format(**locals()) : u"({query.query})".format(**locals())
                for query in queries if query.declared_label}
                
    # update queries
    for query in queries:
        q = query.query
        for lookup in (q_lookup, cb_lookup):
            for k, v in lookup.iteritems():
                q = q.replace(k, v)
        if set(q) & set("{}"):
            m = re.search(r"{(.*?)}", q)
            if m: raise Exception("Cannot find code {} in specified codebook".format(m.group(1)))
            m = re.search(r"{(.*?)}", q)
            if m: raise Exception("Cannot find query {}".format(m.group(1)))
            raise Exception("Mismatches or unknown code lookup in query {q!r}".format(**locals()))
            
        yield SearchQuery(q, query.declared_label)

