from __future__ import with_statement
from threading import Lock
from contextlib import contextmanager
import dbtoolkit

class PooledDB(dbtoolkit.amcatDB):
    def __init__(self, configuration=None, profile=False, nconnections=None):
        self.configuration = configuration
        self.nconnections = nconnections
        self.init(profile=profile)
    def init(self, *args, **kargs):
        self.pool = ResourcePool(self.createConnection, self.nconnections)
        print ">> pool created"
        dbtoolkit.amcatDB.init(self, *args, **kargs)
    def createConnection(self):
        print "Creating new connection"
        return self.connect(self.configuration)
    
    @contextmanager
    def cursor(self):
        c = None
        with self.pool.get() as conn:
            try:
                c = conn.cursor()
                yield c
            except Exception, e:
                print e
                yield None
            finally:
                if c is not None: 
                    try:
                        cursor.close()
                    except:
                        pass
    # transactions not supported due to multi-connection issues
    def commit(self):
        pass
    def rollback(self):
        abstract

    def __getstate__(self):
        print ">>>> __getstate__"
        d = dict(self.__dict__.items())
        for delprop in 'pool', 'DB_LOCK':
            if delprop in d: del d[delprop]
        return d
    def __setstate__(self, d):
        print ">>>> __setstate__"
        self.__dict__ = d
        self.init()

class ResourcePool(object):
    def __init__(self, factory, maxinstances=None):
        self.factory = factory
        self.maxinstances = maxinstances
        self.pool = {} # resource : lock
    def getResource(self):
        for resource, lock in self.pool.iteritems():
            if lock.acquire(False):
                return resource
        if (self.maxinstances is None) or (len(self.pool) < self.maxinstances):
            resource = self.factory()
            if resource is None: raise Exception("Resource Factory returned None")
            l = Lock()
            l.acquire()
            self.pool[resource] = l
            return resource
        return None
    def releaseResource(self, resource):
        self.pool[resource].release()
    @contextmanager
    def get(self):
        try:
            res = self.getResource()
            yield res
        finally:
            if res is not None:
                self.releaseResource(res)
               
if __name__=='__main__':
    db = PooledDB()
    print db.doQuery("select top 10 * from projects")
    with db.cursor():
        print db.doQuery("select top 10 * from projects")
            
    

        
