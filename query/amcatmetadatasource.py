""" 
The amcatmetadatasource class creates a mapping between the metadata 
of articles in the amcat database, and the articles.
"""


import collections, datetime, mx.DateTime
import xapian, dbtoolkit, toolkit, sources, project, article 

from datasource import DataSource, Mapping, Field, FieldConceptMapping
from itertools import imap, izip

#SQL queries for finding the date formats
WEEKSQL = "cast(datepart(year, %(table)s.date) as varchar) + '/' + REPLICATE(0,2-LEN(cast(datepart(week, %(table)s.date) as varchar)))+ CONVERT(VARCHAR,cast(datepart(week, %(table)s.date) as varchar))"
DATESQL = "convert(datetime, convert(int, %(table)s.date))"
WEEKSQL = "datepart(year, %(table)s.date) * 100 + datepart(week, %(table)s.date)"
YEARSQL = "datepart(year, %(table)s.date)"
WEEKSQL = "DATEADD(wk, DATEDIFF(wk, 0, %(table)s.date), 0)"

class DateMapper(object):
    def map(self, date, reverse):
        if reverse:
            return datetime.date(date.year, date.month, date.day)
        else:
            return mx.DateTime.Date(date.year, date.month, date.day)

class ConceptMapper(object):
    def __init__(self, db, targetclass):
        self.db = db
        self.targetclass = targetclass
    def map(self, value, reverse):
        if not reverse: return value.id
        return self.targetclass(self.db, value)    
	
class AmcatMetadataSource(DataSource):
    """
    db := dbtoolkit.amcatDB connection
    datamodel := the draft datamodel
    Returns a mapping of all metadatafields of an article
    """
    def __init__(self, db, datamodel): 
        self.db = db
	DataSource.__init__(self, self.createMappings(datamodel))
    def createMappings(self, datamodel):
        articlefield = DatabaseField(self, datamodel.getConcept("article"), ["articles", "storedresults_articles"], "articleid", ConceptMapper(self.db, article.Article))
        batch = DatabaseField(self, datamodel.getConcept("batch"), ["articles", "batches"], "batchid", ConceptMapper(self.db, project.Batch))
        headline = DatabaseField(self, datamodel.getConcept("headline"), ["articles"], "headline")
        date = DatabaseField(self, datamodel.getConcept("date"), ["articles"], DATESQL, DateMapper())
        week = DatabaseField(self, datamodel.getConcept("week"), ["articles"], WEEKSQL, DateMapper(), sqlmethod=True)
        year = DatabaseField(self, datamodel.getConcept("year"), ["articles"], YEARSQL)
        source = DatabaseField(self, datamodel.getConcept("source"), ["articles","media"], "mediumid", ConceptMapper(self.db, sources.Source))
        url = DatabaseField(self, datamodel.getConcept("url"), ["articles"], "url")
        projectfield = DatabaseField(self, datamodel.getConcept("project"),["batches"], "projectid", ConceptMapper(self.db, project.Project))
        sourcetype = DatabaseField(self, datamodel.getConcept("sourcetype"),["media"], "type")
        storedresult = DatabaseField(self,datamodel.getConcept("storedresult"),["storedresults_articles"],"storedresultid")
        
        return [
          DatabaseMapping(articlefield, batch),
          DatabaseMapping(articlefield, date, 1, 9999),
          DatabaseMapping(articlefield, week, 1, 999999),
          DatabaseMapping(articlefield, year, 1, 99999),
          DatabaseMapping(articlefield, source),
          DatabaseMapping(articlefield, url),
          DatabaseMapping(batch, projectfield),
          DatabaseMapping(articlefield, headline),
          DatabaseMapping(source, sourcetype),
          DatabaseMapping(articlefield,storedresult)
          ]
    def deserialize(self, concept, id):
        f = self.getDatabaseField(concept)
        if f: return f.deserialize(id)
        
    def __str__(self):
        return "Amcat"

    def getDatabaseField(self, concept):
        for mapping in self.getMappings():
            for field in (mapping.a,mapping.b):
                if isinstance(field, DatabaseField) and field.concept == concept:
                    return field


class DatabaseField(Field):
    def __init__(self, datasource, concept, tables, column, conceptmapper=None, sqlmethod=False):
        Field.__init__(self, datasource, concept)
        self.tables = tables
        self.column = column
        self.conceptmapper = conceptmapper
        self.sqlmethod = sqlmethod
    def getConceptMapping(self):
        return FieldConceptMapping(self.concept, self, self.mapConcept)
    def mapConcept(self, value, reverse):
        if self.conceptmapper:
            return self.conceptmapper.map(value, reverse)
        return value
    def getColumn(self, table):
        if "%(table)s" in self.column or self.sqlmethod:
            return self.column % dict(table=table)
        else:
            return "%s.%s" % (table, self.column)
    def getJoins(self):
        for i, t in enumerate(self.tables):
            for t2 in self.tables[i+1:]:
                yield (t, t2, self.column)
    def deserialize(self, value):
        if type(value) == int and self.conceptmapper:
            return self.conceptmapper.map(value, True)

class DatabaseMapping(Mapping):
    def __init__(self, a, b, cost=1.0, reversecost=None):
        Mapping.__init__(self, a, b, cost, reversecost or cost)
    def map(self, value, reverse, memo=None):
        if memo is None:
            memo = self.startMapping([value], reverse=reverse)
        return memo[value]

    def getTable(self):
        tables = set(self.a.tables) & set(self.b.tables)
        if len(tables) <> 1: raise Exception("Intersection not one!")
        return tables.pop()
    def startMapping(self, values,reverse):
        table = self.getTable()
        
        selectcol = self.a.getColumn(table) if reverse else self.b.getColumn(table)
        filtercol = self.b.getColumn(table) if reverse else self.a.getColumn(table)
        values = list(set(values))
        result_dict = collections.defaultdict(list)
        for values in toolkit.splitlist(values, 1000):
            valuestr = ",".join(map(toolkit.quotesql, values))
            sql_query = "select %s, %s  from %s where %s in (%s)" % (filtercol,selectcol, table, filtercol, valuestr)
            for k, v in self.a.datasource.db.doQuery(sql_query):
                result_dict[k].append(v)

        return result_dict
        
if __name__ == '__main__':
    import dbtoolkit
    db = dbtoolkit.amcatDB()
    
    from mst import getSolution
    from datasource import FunctionalDataModel
    import tabulator
    
    dm = FunctionalDataModel(getSolution)
    ads = AmcatMetadataSource(db, dm)
    dm.register(ads)
    
    print dm.getConcepts()
    
    project = dm.getConcept("project")
    art = dm.getConcept("article")
    medium = dm.getConcept("source")
    mediumtype = dm.getConcept("sourcetype")
    filters = {project : [368], art : [44134082,44135035, 44126401]  }
    select = [art, project, mediumtype]

    data = tabulator.tabulate(dm, select, filters)

    print " | ".join(map(lambda x: "%-15s" % x, select))
    print "-+-".join(["-"*15 for x in select])
    for row in data:
        print " | ".join(map(lambda x: "%-15s" % x, row))
