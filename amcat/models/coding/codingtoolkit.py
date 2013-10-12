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
Convenience functions to extract information about codings
"""

from __future__ import unicode_literals, print_function, absolute_import

from functools import partial

from amcat.models.coding.codingjob import CodingJob
from amcat.models.coding.coding import Coding, CodingStatus, STATUS_COMPLETE, CodingValue
from amcat.models.coding.codedarticle import CodedArticle, bulk_create_codedarticles
from amcat.models.coding.code import Code
from amcat.models.coding.codingschemafield import CodingSchemaField
from amcat.models.coding.codingschemafield import CodingSchemaFieldType
from django import forms

from amcat.tools.table.table3 import ObjectTable, ObjectColumn

import logging; log = logging.getLogger(__name__)

def get_table_jobs_per_user(users, **additionalFilters):
    """Return a table of all jobs per user

    Columns: ids, jobname, coder, issuer, issuedate, #articles, #completed, #inprogress
    """
    try: iter(users)
    except TypeError: users = [users]
    jobs = list(CodingJob.objects.filter(coder__in=users, **additionalFilters).order_by("-id"))
    result = ObjectTable(rows=jobs)
    result.addColumn("id")
    result.addColumn("name")
    result.addColumn("coder")
    result.addColumn(lambda s: s.insertuser, "insertuser")
    result.addColumn(lambda s :s.insertdate, "insertdate")
    result.addColumn(lambda s :s.articleset.articles.count(), "narticles")
    result.addColumn(lambda s :s.codings.filter(sentence=None, status=2).count(),
                     "ncomplete")
    return result

def get_article_coding(job, article):
    """Find the 'article coding' for the given article"""
    result = job.codings.filter(article=article, sentence=None)
    assert len(result) <= 1
    if result: return result[0]

def get_coded_articles(jobs, cache_sentences=False, cache_coding=False, select_related=None):
    """Return a sequence of CodedArticle objects"""
    try: iter(jobs)
    except TypeError: jobs = [jobs]
    for job in jobs:
        # Determine if articles need custom caching
        articles = select_related if select_related is None else (
            job.articleset.articles.all().select_related(*select_related)
        )

        for ca in bulk_create_codedarticles(job, cache_sentences, cache_coding, articles):
            yield ca

def get_table_articles_per_job(jobs):
    """Return a table of all articles in a cjset with status

    Columns: article, articlemeta, status, comments
    """
    result = ObjectTable(
        rows=list(get_coded_articles(
            jobs, cache_coding=True, select_related=("medium",)
        ))
    )
    result.addColumn(lambda a: a.article.id, "articleid")
    result.addColumn(lambda a: a.article.headline, "headline")
    result.addColumn(lambda a: a.article.date, "date")
    result.addColumn(lambda a: a.article.medium, "medium")
    result.addColumn(lambda a: a.article.pagenr, "pagenr")
    result.addColumn(lambda a: a.article.length, "length")
    result.addColumn(lambda a: a.coding and a.coding.status, "status")
    result.addColumn(lambda a: a.coding and a.coding.comments, "comments")
    return result

class CodingColumn(ObjectColumn):
    def __init__(self, field, language):
        super(CodingColumn, self).__init__(field.label)
        self.field = field
        self.language = language
    def getCell(self, coding):
        try:
            value = coding.values.get(field_id=self.field.id)
            value = value.value
        except (CodingValue.DoesNotExist, Code.DoesNotExist):
            value = None # field is not coded yet or codebook/schema change
        if value is None: return ''
        return self.field.serialiser.value_label(value, self.language)
    
def get_table_sentence_codings_article(codedarticle, language):
    """Return a table of sentence codings x fields

    The cells contain domain (deserialized) objects
    """
    result = ObjectTable(rows = list(codedarticle.sentence_codings))
    result.addColumn('id')
    result.addColumn(lambda x:x.sentence_id, 'sentence')
    for field in codedarticle.codingjob.unitschema.fields.order_by('fieldnr').all():
        result.addColumn(CodingColumn(field, language))
    return result

def _getFieldObj(field):
    """returns a matching Django Field object 
    for a amcat.models.coding.codingschemafield.CodingSchemaField object"""

    global CB_TYPE
    if CB_TYPE is None:
        CB_TYPE = CodingSchemaFieldType.objects.get(name="Codebook")

    
    yield forms.CharField(label=field.label, initial=field.default,
                            widget=forms.TextInput(), required=field.required)

    
    if field.fieldtype == CB_TYPE and field.split_codebook:
        print(field)
        
        
class CodingSchemaForm(forms.Form):
    """Dummy form that should be initiated with dynamic fields, based on the coding schema
    
    Requires as first argument an AnnotationSchema"""

    def __init__(self, schema, *args, **kargs):
        super(CodingSchemaForm, self).__init__(*args, **kargs)
        for field in schema.fields.order_by('fieldnr').all():
            for i, _field in enumerate(_getFieldObj(field)):
                _id = "field_{field.id}" 
                if i: _id += "_{i}"
                self.fields[_id.format(**locals())] = _field
            
class CodingStatusCommentForm(forms.Form):
    """Form that represents the coding status and comment"""

    comment = forms.CharField(label='Comment', required=False, widget=forms.Textarea(attrs={'rows':4, 'cols':40}))
    status = forms.ModelChoiceField(queryset=CodingStatus.objects.all(), empty_label=None)
    
        
###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################
        
from amcat.tools import amcattest

class TestCodingToolkit(amcattest.PolicyTestCase):

    def setUp(self):
        from amcat.models.coding.coding import CodingValue
        # create a coding job set with a sensible schema and some articles to 'code'
        self.schema = amcattest.create_test_schema()
        self.codebook = amcattest.create_test_codebook()
        self.code = amcattest.create_test_code(label="CODED")
        self.codebook.add_code(self.code)
        

        texttype = CodingSchemaFieldType.objects.get(pk=1)
        inttype = CodingSchemaFieldType.objects.get(pk=2)
        codetype = CodingSchemaFieldType.objects.get(pk=5)

        create = CodingSchemaField.objects.create
        self.textfield = create(codingschema=self.schema, fieldnr=1, fieldtype=texttype, 
                                label="Text")
        self.intfield = create(codingschema=self.schema,  fieldnr=2, fieldtype=inttype, 
                               label="Number")
        self.codefield = create(codingschema=self.schema, fieldnr=3, fieldtype=codetype, 
                                label="Code", codebook=self.codebook)

        self.users = [amcattest.create_test_user() for _x in range(2)]

        self.articles, self.jobs, self.asets = [], [], []
        for i, user in enumerate([0, 0, 0, 0, 1]):
            aset = amcattest.create_test_set(articles=2 * (i+1))
            self.articles += list(aset.articles.all())
            self.asets.append(aset)
            job = amcattest.create_test_job(articleschema=self.schema, unitschema=self.schema,
                                            coder = self.users[user], articleset=aset)
            self.jobs.append(job)
                    
        self.an1 = Coding.objects.create(codingjob=self.jobs[0], article=self.articles[0])
        self.an2 = Coding.objects.create(codingjob=self.jobs[0], article=self.articles[1])
        self.an2.set_status(STATUS_COMPLETE)
        self.an2.comments = 'Makkie!'
        self.an2.save()

        sent = amcattest.create_test_sentence()
        self.sa1 = Coding.objects.create(codingjob=self.jobs[0], article=self.articles[0], 
                                             sentence=sent)
        self.sa2 = Coding.objects.create(codingjob=self.jobs[0], article=self.articles[0], 
                                             sentence=sent)
        create = CodingValue.objects.create
        create(coding=self.sa1, field=self.intfield, intval=1)
        create(coding=self.sa1, field=self.textfield, strval="bla")
        create(coding=self.sa2, field=self.textfield, strval="blx")
        create(coding=self.sa1, field=self.codefield, intval=self.code.id)

        
        
    def test_general(self):
        """Test whether the setUp works"""
        self.assertEqual(self.jobs[0].coder, self.users[0])

        
    def test_table_codings(self):
        """Is the codings table correct?"""
        ca = CodedArticle(self.an1)
        t = get_table_sentence_codings_article(ca, ca.codingjob.coder.userprofile.language)
        self.assertIsNotNone(t)
        aslist1 = [a for _, a in t.getRows()[0].get_values()]
        self.assertEqual(aslist1, ['bla', 1, self.code])
        #TODO: this does not work (anymore?)
        #aslist2 = [a for _, a in t.getRows()[1].get_values()]
        #self.assertEqual(aslist2, ['blx', None, None])
        
    def test_table_articles_per_set(self):
        """Is the articles per job table correct?"""
        t = get_table_articles_per_job([self.jobs[i] for i in [0, 1]])
        #from amcat.tools.table import tableoutput; print; print(tableoutput.table2unicode(t))
        #self.assertEqual([row.codingjob for row in t], [self.jobs[i] for i in [0] * 6])
        self.assertEqual(sorted((row.status and row.status.id) for row in t), sorted([0, 2]+[None]*4))
        

    def todo_test_get_coded_articles(self):
        """Test the get_coded_articles function"""
        result = list(get_coded_articles(self.jobs[i] for i in [0, 1]))
        jobs = [self.jobs[i] for i in (0, 0, 1, 1, 1, 1)]
        articles = [self.articles[i] for i in range(6)]
        codings = [self.an1, self.an2] + [None]*4
        self.assertEqual(len(result), len(jobs))
        for result, job, article, coding in zip(result, jobs, articles, codings):

            ca = CodedArticle(job, article)
            self.assertEqual(ca, result)
            self.assertEqual(coding, result.coding)


    def test_get_article_coding(self):
        """Correctly identify the article coding for an article"""
        self.assertEqual(self.an1, get_article_coding(self.jobs[0], self.articles[0]))
        self.assertIsNone(get_article_coding(self.jobs[1], self.articles[2]))
        
    def test_table_jobs_per_user(self):
        """Is the sets per user table correct"""
        t = get_table_jobs_per_user(self.users[0])
        #from amcat.tools.table.tableoutput import table2unicode; print(table2unicode(t))
        self.assertEqual(len([row.id for row in t]), 4)
        self.assertEqual([row.narticles for row in t], [8, 6, 4, 2]) # default newest job first
        
        self.assertIsNotNone(t)

        
    def test_nqueries_table_sentence_codings(self):
        """Check for efficient retrieval of codings"""
        from amcat.models.coding.coding import CodingValue
        from amcat.tools.djangotoolkit import list_queries
        ca = CodedArticle(self.an1)

        # create 1000 sentence annotations
        for i in range(1):
            sent = amcattest.create_test_sentence()
            sa = Coding.objects.create(codingjob=self.jobs[0], article=self.articles[0], 
                                       sentence=sent)
            CodingValue.objects.create(coding=sa, field=self.intfield, intval=i)
        
        with list_queries() as l:
            t = get_table_sentence_codings_article(ca, ca.codingjob.coder.userprofile.language)
            t.output() # force getting all values
	#query_list_to_table(l, output=print, maxqlen=190)
        self.assertTrue(len(l) < 30, "Retrieving table used %i queries" % len(l))

        
