from cachable import Cachable, DBFKPropertyFactory, DBPropertyFactory, CachingMeta, cache
import cachable
import toolkit
try:
    import mx.DateTime as my_datetime
except:
    from datetime import datetime as my_datetime
    
def getParent(db, cid, pid):
    cl = Class(db, cid)
    if pid is None:
        return cl, None
    return cl, Object(db, pid)

    #return Class(db, cid), pid and Object(db, pid)

def getAllAncestors(object, stoplist=None, golist=None):
    if stoplist is None: stoplist = set()
    for p in object.getAllParents():
        if (p is None) or (p in stoplist): continue
        if (golist and p not in golist): continue
        yield p
        stoplist.add(p)
        for o2 in getAllAncestors(p, stoplist, golist):
            yield o2

def getAllDescendants(object, stoplist=None, golist=None):
    if stoplist is None: stoplist = set()
    for p in object.children:
        if (p is None) or (p in stoplist): continue
        if (golist and p not in golist): continue
        yield p
        stoplist.add(p)
        for o2 in getAllDescendants(p, stoplist, golist):
            yield o2

def getObject(db, id):
    return Object(db, id)

DATEFILTER = "fromdate < %s and (todate is null or todate > %s)" % (toolkit.quotesql(my_datetime.now()), toolkit.quotesql(my_datetime.now()))

class Function(object):
    def __init__(self, db, functionid, office_objectid, fromdate, todate):
        self.functionid = functionid
        self.office = Object(db, office_objectid)
        if fromdate.year == 1753: fromdate = None
        self.fromdate = fromdate
        self.todate = todate
        self.klass = Class(db, 1) if self.functionid==0 else Class(db, 2) 
    def __str__(self):
        return "Function(%s, %s, %s, %s)" % (self.functionid, self.office, self.fromdate and toolkit.writeDate(self.fromdate), self.todate and toolkit.writeDate(self.todate))
    __repr__ = __str__

class Object(Cachable):
    __table__ = 'o_objects'
    __idcolumn__ = 'objectid'
    __metaclass__ = CachingMeta

    labels = DBFKPropertyFactory("o_labels", ("languageid", "label"), endfunc=dict)
    parents = DBFKPropertyFactory("o_hierarchy", ("classid", "parentid"), reffield="childid", dbfunc = getParent, endfunc=dict)
    children = DBFKPropertyFactory("o_hierarchy", ("classid", "childid"), reffield="parentid", dbfunc = getParent, endfunc=toolkit.multidict)

    name = DBPropertyFactory("name", table="o_politicians")
    firstname = DBPropertyFactory("firstname", table="o_politicians")
    prefix = DBPropertyFactory("prefix", table="o_politicians")
    keyword = DBPropertyFactory(table="o_keywords")


    functions = DBFKPropertyFactory("o_politicians_functions", ("functionid", "office_objectid", "fromdate", "todate"), dbfunc = Function)

    def __init__(self, db, id, languageid=2, **cache):
        Cachable.__init__(self, db, id, **cache)
        self.addDBProperty("label", table="dbo.fn_o_labels(%i)" % languageid)

    def getAllParents(self, date=None):
        for c, p in self.parents.iteritems():
            yield c, p
        for f in self.currentFunctions(date):
            yield f.klass, f.office
        
    def currentFunctions(self, date=None):
        if not date: date = my_datetime.now()
        for f in self.functions:
            if f.fromdate and date < f.fromdate: continue
            if f.todate and date >= f.todate: continue
            yield f
    
    def getSearchString(self, date=None, xapian=False, languageid=None, fallback=False):
        """Returns the search string for this object.
        date: if given, use only functions active on this date
        xapian: if true, do not use ^0 weights
        languageid: if given, use labels.get(languageid) rather than o_keywords"""
        
        if not date: date = my_datetime.now()
        if languageid:
            kw = self.labels.get(languageid)

        if (not languageid) or (fallback and kw is None):
            kw = self.keyword
        
        if not kw and self.name:
            ln = self.name
            if "-" in ln or " " in ln:
                ln = '"%s"' % ln.replace("-", " ")
            conds = []
            if self.firstname:
                conds.append(self.firstname)
            for function in self.currentFunctions(date):
                k = function.office.getSearchString()
                if not k: k = '"%s"' % str(function.office).replace("-"," ")
                conds.append(k)
                conds += function2conds(function)
            if conds:
                if xapian:
                    kw = "%s AND (%s)" % (ln, " OR ".join("%s" % x.strip() for x in conds),)
                else:
                    kw = "%s AND (%s)" % (ln, " OR ".join("%s^0" % x.strip() for x in conds),)
            else:
                kw = ln
        if kw:
            if type(kw) == str: kw = kw.decode('latin-1')
            return kw.replace("\n"," ")


def function2conds(function):
    officeid = function.office.id
    if officeid in (380, 707, 729, 1146, 1536, 1924, 2054, 2405, 2411, 2554, 2643):
        if function.functionid == 2:
            return ["bewinds*", "minister*"]
        else:
            return ["bewinds*", "staatssecret*"]

    if officeid == 901:
        return ["premier", '"minister president"']
    if officeid == 548:
        return ["senator", '"eerste kamer*"']
    if officeid == 1608:
        return ["parlement*", '"tweede kamer*"']
    if officeid == 2087:
        return ['"europ* parlement*"', "europarle*"]
    return []

class Hierarchy(object):
    """
    Interface for hierarchies (ie classes and sets).
    Hierarchies should be consistent, ie the following should always be true:
    head(h.getRoots()).getParent() is None
    h.getParent(head(getChildren(o))) == o
    h.getParent(o) is None or head(h.getChildren(h.getParent(o))) == o
    Also, there should be no parent of child cycles, and every object in h must be reachable
    using repeated getChildren calls on the roots and vice versa
    """
    def __init__(self):
        self.categorisationcache = {} # objectid : path
    def getParent(self, object, date=None):
        """Returns a BoundObject representing the parent of the given (Bound)Object in this hierarchy"""
        abstract
    def getChildren(self, object):
        """
        Returns a sequence of BoundObjects representing the children of the given (Bound)Object in this hierarchy
        """
        abstract
    def getObjects(self):
        """Return a sequence of BoundObjects represnting all Objects in this hierarchy"""
        abstract
    def cacheHierarchy(self):
        """Optional  method to ask the Hierarchy to cache all objects and child/parent relations"""
        pass
    def getRoots(self):
        """returns a sequence of BoundObjects representing the root(s) of this hierarchy"""
        for o in self.getObjects():
            if not self.getParent(o):
                yield o
    def __contains__(self, object):
        """Checks whether the given (Bound)Object is included in this hierarchy"""
        abstract
    def getBoundObject(self, object_or_id):
        """Returns a BoundObject representing the given object (or objectid/boundobject)"""
        abstract
    def getClass(self, object):
        """Returns the Class object that is best seen as this objects class in this hierarchy"""
        abstract
        
    def getIndentedList(self, cachefirst = True):
        if cachefirst: self.cacheHierarchy()
        def recurse(o):
            yield o, 0
            for o2 in self.getChildren(o):
                for o3, i in recurse(o2):
                    yield o3, i+1
        for r in self.getRoots():
            for c, indent in recurse(r):
                yield c,indent

    def getCategorisationPath(self, object, date=None):
        if object.id not in self.categorisationcache:
            object = self.getBoundObject(object) 
            path = [object] 
            while True:
                p = self.getParent(path[-1], date)
                if p is None: break
                path.append(p)
            path.append(self.getClass(path[-1]))
            self.categorisationcache[object.id] = path
        return self.categorisationcache[object.id]
                
    def categorise(self, object, date=None, depth=[0,1,2], returnObjects=True, returnOmklap=False):
        object = self.getBoundObject(object)
        path = self.getCategorisationPath(object, date)
        if returnOmklap:
            omklap = 1
            for p, c in zip(path[1:-1], path[:-2]):
                omklap *= getOmklap(self.db, p, c)
            
        l = max(depth)+1
        path = [object] * (l - len(path)) + path
        path = [path[-1-d] for d in depth]

        if returnObjects and returnOmklap:
            return path, omklap
        elif returnOmklap:
            return omklap
        return path
    
_omklaps = None
def getOmklap(db, parent, child):
    global _omklaps
    if _omklaps is None:
        _omklaps = set(db.doQuery("select parentid, childid from o_hierarchy where reverse = 1"))
        print _omklaps
    if (parent.id, child.id) in _omklaps: return -1
    return 1
            

class DictHierarchy(Hierarchy):
    """Abstract Hierarchy subclass that uses a dictionary to keep track of contained objects"""
    def __init__(self, *args, **kargs):
        Hierarchy.__init__(self, *args, **kargs)
        self.objectdict = None # {id : BoundObject}
    def __contains__(self, object):
        if object is None: return False
        if self.objectdict is None: self.cacheHierarchy()
        if type(object) <> int: object = object.id
        return object in self.objectdict
    def getBoundObject(self, object_or_id):
        if object_or_id is None: return
        if self.objectdict is None: self.cacheHierarchy()
        if type(object_or_id) <> int: object_or_id = object_or_id.id
        if object_or_id not in self.objectdict:
            toolkit.warn("Unknown objectid: %i" % object_or_id)
        return self.objectdict.get(object_or_id)
    def cacheHierarchy(self):
        if self.objectdict is not None: return
        self.objectdict = {}
        super(DictHierarchy, self).cacheHierarchy()
        for obj in self.objects:
            self.objectdict[obj.id] = BoundObject(self, obj)
    def getObjects(self):
        if self.objectdict is None: self.cacheHierarchy()
        return self.objectdict.values()
        

class BoundObject(toolkit.IDLabel):
    """
    Represents an object 'bound' to a hierachy, ie with a unique parent and sequence of children
    """
    def __init__(self, hierarchy, objekt):
        toolkit.IDLabel.__init__(self, objekt.id, label=None)
        self.hierarchy = hierarchy
        self.objekt = objekt
    def getParent(self, date=None):
        return self.hierarchy.getParent(self, date)
    def getChildren(self):
        return self.hierarchy.getChildren(self)
    @property
    def label(self):
        return self.objekt.label
    def __str__(self):
        return str(self.objekt)
    def getSearchString(self, *args, **kargs):
        return self.objekt.getSearchString( *args, **kargs)
#    def __getattr__(self, attr):
#        return self.objekt.__getattribute__(attr)
#    def __getattr__(self, attr):
#        if attr == "objekt": return super(BoundObject, self).__getattr__('objekt')
#        return self.objekt.__getattribute__(attr)

def getBoundObject(hierarchy, id):
    return hierarchy.getBoundObject(id)

class Class(Cachable, DictHierarchy):
    __table__ = 'o_classes'
    __idcolumn__ = 'classid'
    __dbproperties__ = ["label"]
    objects = DBFKPropertyFactory("o_hierarchy", "childid", dbfunc=Object)
    def __init__(self, db, id, **cache):
        Cachable.__init__(self, db, id, **cache)
        DictHierarchy.__init__(self)
    def getRoots(self, cachefirst=True):
        if cachefirst: self.cacheHierarchy()
        for o in self.getObjects():
            if not o.getParent():
                yield o
    def getChildren(self, object):
        if type(object) == BoundObject: object = object.objekt
        children = object.children.get(self)
        if children:
            for c in children:
                yield self.getBoundObject(c)
    def getParent(self, object, date=None):
        if type(object) == BoundObject: object = object.objekt
        p = object.parents.get(self)
        if p:
            return self.getBoundObject(p)
    def cacheHierarchy(self):
        #raise Exception("CACHE CLASS???!?")
        cache(self.objects, "parents", "label", "children")
        super(Class, self).cacheHierarchy()
    def getClass(self, object):
        return self
        
class Set(Cachable, DictHierarchy):
    __table__ = 'o_sets'
    __idcolumn__ = 'setid'
    __dbproperties__ = ["name"]
    __metaclass__ = CachingMeta
    objects = DBFKPropertyFactory("o_sets_objects", "objectid", dbfunc=Object)
    classes = DBFKPropertyFactory("o_sets_classes", "classid", dbfunc=Class, orderby="rank")
    def __init__(self, db, id, **cache):
        Cachable.__init__(self, db, id, **cache)
        DictHierarchy.__init__(self)
    def getParent(self, o, date=None):
        if type(o) == BoundObject: o = o.objekt 
        parents = dict(o.getAllParents(date))
        
        for c in self.classes:
            o2 = parents.get(c)
            if o2 in self:
                return self.getBoundObject(o2)
    def getChildren(self, o):
        yielded = set()
        for c in self.classes:
            for o2 in c.getChildren(o):
                if o2 in yielded: continue
                if o2 not in self: continue
                p = self.getParent(o2)
                if p and p.id == o.id:
                    yielded.add(o2)
                    yield self.getBoundObject(o2)
    def cacheHierarchy(self):
        print "Caching set %s!" % self.id
        cachable.cacheMultiple(self, "objects", "classes")
        fields = ["parents", "children", "label"]
        if set((1,2)) & set(c.id for c in self.classes):
            fields.append("functions")
        cachable.cacheMultiple(self.objects, *fields)
        for c in self.classes:
            c.cacheHierarchy() # TODO: only need membership
        super(Set, self).cacheHierarchy()
    def cacheLabels(self):
        cachable.cache(self, objects=["label"])
        
    def getClass(self, object):
        for c in self.classes:
            if object in c:
                return c
    
if __name__ == '__main__':
    import dbtoolkit, pickle, cachable

    db = dbtoolkit.amcatDB(profile=True)
    db.beforeQueryListeners.add(lambda a: toolkit.ticker.warn(a[:250]))

    o = Object(db, 15770)
    s = Set(db, 5001)
    s.cacheHierarchy()
    
    path, omklap = s.categorise(o, returnOmklap = True)
    print omklap, map(str, path)

    #s = Set(db, 201)
    #print map(str, s.categorise(10283))
    
    db.printProfile()
