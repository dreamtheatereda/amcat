HOST = 'amcat.vu.nl'

from servertools import *
import socketio
import datamodel
from enginebase import QueryEngineBase, ConceptTable, postprocess
import filter
import tableserial

class ProxyEngine(QueryEngineBase):
    def __init__(self, datamodel, log=False, profile=False, port=PORT, idlabelfactory=None):
        self.port = port
        QueryEngineBase.__init__(self, datamodel, log, profile)
        self.idlabelfactory = idlabelfactory

    def connect(self):
        s = socketio.connect(HOST, self.port)
        clienthandshake(s)
        return s
        
    def getList(self, concepts, filters, sortfields=None, limit=None, offset=None, distinct=False):
        sock = self.connect()
        data = queryList(sock, concepts, filters, distinct, self.idlabelfactory)
        if not data: data = []
        result = ConceptTable(concepts, data)
        print "Received table with %i rows" % len(result.data)
        postprocess(result, sortfields, limit, offset)
        return result

    def getQuote(self, aid, *words):
        words = " ".join(words)
        sock = self.connect()
        sock.sendint(REQUEST_QUOTE)
        sock.sendint(aid)
        sock.sendstring(words)
        sock.flush()
        return sock.readstring()

def authenticateToServer(socket):
    challenge = socket.readstring()
    response = hash(challenge)
    #print "Received challenge %r, hashed with key %r, response is %r" % (challenge, KEY, response)
    socket.write(response)
    socket.flush()
def clienthandshake(socket):
    print "Sending version no"
    socket.sendint(1) # version no
    socket.flush()
    print "Reading server version"
    serverversion = socket.readint(checkerror=True)
    print "Connected to AmCAT EngineServer version %i" % serverversion
    authenticateToServer(socket)
    serverok = socket.readint(checkerror=True)
    if serverok<>1: raise Exception("Server returned invalid OK status %i" % serverok)
    print "Server ok: %i" % serverok

def queryList(socket, concepts, filters, distinct=False, idlabelfactory=None):
    socket.sendint(REQUEST_LIST_DISTINCT if distinct else REQUEST_LIST)
    print ">>>", REQUEST_LIST_DISTINCT if distinct else REQUEST_LIST
    socket.sendint(len(concepts))
    socket.sendint(len(filters))
    for c in concepts:
        socket.sendstring(c.label)
    for f in filters:
        print "Sending filter %s" % f
        if isinstance(f, filter.IntervalFilter):
            filterid, data = FILTER_INTERVAL, [[f.fromValue], [f.toValue]]
        else:
            filterid, data = FILTER_VALUES, [[x] for x in f.values]
        socket.sendint(filterid) 
        socket.sendstring(f.concept.label)
        tableserial.serialiseData([f.concept], data, socket)
    socket.flush()
    
    return tableserial.deserialiseData(socket, concepts, idlabelfactory)
    
                               
if __name__ == '__main__':
    import sys; port = int(sys.argv[1])
    dm = datamodel.DataModel()
    p = ProxyEngine(dm, port=port)
    from filter import *
    #p.getList([dm.article, dm.url], [])
    #p.getList([dm.article, dm.headline, dm.date, dm.sourcetype, dm.project, dm.source], [filter.ValuesFilter(dm.storedresult, 958), filter.IntervalFilter(dm.date, '2010-01-01','2010-12-10')])
    #t = p.getList([dm.source], [filter.ValuesFilter(dm.storedresult, 958), filter.IntervalFilter(dm.date, '2010-01-01','2010-12-10')], distinct=True, limit=3)
    #t = p.getList([dm.article], [ValuesFilter(dm.article, 46599856), ValuesFilter(dm.brand, 16545)])
    t = p.getList([dm.article], [ValuesFilter(dm.article, 7777777)])
    import tableoutput; print tableoutput.table2ascii(t)

