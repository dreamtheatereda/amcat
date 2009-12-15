import toolkit, dbtoolkit, re, sbd, ctokenizer, mx.DateTime, sources, types, project, weakref, binascii
from toolkit import cached
from itertools import izip, count
_debug = toolkit.Debug('article',1)
#_xmltemplatefile = '/home/anoko/resources/files/article_template.xml'

class Article(object):
    """
    Class representing a newspaper article
    """
    xmltemplate = None

    def __init__(self, db, id, batchid, medium, date, headline, length, pagenr, encoding = None):
        self.db         = db
        self.id         = id
        self.batchid    = batchid
        self.medium     = medium
        self.date       = date
        self.headline   = headline
        self.length     = length
        self.pagenr     = pagenr

        self.encoding = encoding
        if encoding: self.headline = dbtoolkit.decode(self.headline, encoding)
        elif headline: self.headline = self.headline.decode('latin-1')
        
        self._byline, self._section, self._fullmeta, self._url = None, None, None, None

    @property
    def url(self):
        if not self._url: self._getMeta()
        return self._url
    @property
    def section(self):
        if not self._section: self._getMeta()
        return self._section
    @property
    def byline(self):
        if not self._byline: self._getMeta()
        return self._byline
    @property
    def fullmeta(self):
        if not self._fullmeta: self._getMeta()
        return self._fullmeta
    @property
    def text(self):
        return self.getText()

    def decode(self, s):
        try:
            return dbtoolkit.decode(s, self.encoding)
        except Exception, e:
            return s.decode('latin-1')
            
    
    def _getMeta(self):
        b,s,m,u = self.db.doQuery("select byline, section, metastring, url from articles where articleid=%i" % self.id)[0]
        self._byline = self.decode(b)
        self._section = self.decode(s)
        m = self.decode(m)
        self._fullmeta = toolkit.dictFromStr(m, unicode=True)
        self._url = u

    @property
    @cached
    def project(self):
        pid = self.db.getValue("select projectid from batches where batchid=%i" % self.batchid)
        return project.Project(self.db, pid)

    def getProjectid(self):
        return self.project.id

    def setMeta(self, byline, section, fullmeta):
        if toolkit.isString(fullmeta):
            fullmeta = toolkit.dictFromStr(fullmeta, unicode=True)
        self._meta = {"byline": byline, "section": section, "fullmeta" : fullmeta}

    def getText(self, type=2):
        if not self.id: return ''
        return self.db.getText(self.id, type)

    def getSection(self):
        return self.section
    
    def toText(self):
        return self.fulltext()

    def toHTML(self, limitpars = None, includeMeta = False, includeHeadline = True, includeText = True):
        res = u""
        if includeHeadline:
            res = u"<h1>%s</h1>" % self.headline
            if self.byline:
                res += "\n<h2>%s</h2>" % self.byline
        if includeMeta:
            source = self.db.sources.lookupID(self.medium)
            res += '''<table class="meta">
            <tr><td>Source:</td><td>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>%s</td></tr>
            <tr><td>Date:</td><td></td><td>%s</td></tr>
            <tr><td>Articleid:</td><td></td><td>%s</td></tr>
            <tr><td>Page:</td><td></td><td>%s</td></tr>
            <tr><td>Length:</td><td></td><td>%s</td></tr>
            <tr><td>Section:</td><td></td><td>%s</td></tr>
            </table>''' % (source, toolkit.writeDate(self.date), self.id, self.pagenr, self.length, self.section)
        if includeText and self.text: 
            if limitpars:
                res += "<p>%s</p>" % "</p><p>".join(self.text.split("\n\n")[:limitpars])
            else:
                res += "<p>%s</p>" % "</p><p>".join(self.text.split("\n\n"))
        return res

    """
    def toXML2(self):
        if not self.xmltemplate:
            self.xmltemplate = open(_xmltemplatefile).read()

        text = toolkit.clean(self.headline, level=1)
        for par in sbd.splitPars(self.text, type=self.type, returnSents=False):
            text += "\n\n%s" % toolkit.clean(par, level=1)
        src = self.db.sources.lookupID(self.medium)
        dct = self.__dict__
        dct.update({'source':src.prettyname,'lang':src.language.strip(),'date':toolkit.writeDate(self.date),'text':text})
        return self.xmltemplate % dct

    def toXML(self):
        # gebruik sentences als die er zijn??
        if not self.xmltemplate:
            self.xmltemplate = open(_xmltemplatefile).read()
        src = self.db.sources.lookupID(self.medium)
        text = '''
        <p n="0" function="headline">
           <s id="0">%(headline)s</s>
        </p>''' % self.headline
        np=2; ns = 1;
        if self.byline:
            text += '\n  <p n="1" function="byline">\n   <s id="%s">%s</s>\n  </p>' % (ns, self.byline)
            ns+=1
        content=self.text.replace("q11 \n","\n\n")
        if len(content.strip().split("\n")[0])>100: content = content.replace("\n","\n\n")
        content = re.sub(r"(.{,50}\.)\n",r"\1\n\n",content)
        
        for par in sbd.splitPars(content):
            if not par:continue
            text += '\n  <p n="%s" function="body">' % np
            for line in par:
                if not line:continue
                line=line.replace("-\n","")
                text += '\n   <s id="%s">%s</s>' % (ns, toolkit.clean(line, level=1, droptags=1, escapehtml=1))
                ns += 1
            text += '\n  </p>'
            np += 1
            
        dct = self.__dict__
        dct.update({'source':src.prettyname,'lang':src.language.strip(),'date':toolkit.writeDate(self.date),'text':text})
        
        
        xml = self.xmltemplate % dct
        return '<?xml-stylesheet type="text/xsl" href="http://www.cs.vu.nl/~wva/anoko/article.xsl"?>\n%s'% xml
    """

    def getPagenr(article):
        """
        Returns the pagenr of the article. If None, invokes parseSection
        on the section and returns the pagenr (if found)
        """
        if self.pagenr:
            return self.pagenr
        elif self.section:
            p = toolkit.parseSection(self.section)
            if p:
                self.pagenr = p[1]
                return self.pagenr
            else:
                _debug('Could not parse section "%s" (aid=%s)'  % (self.section, self.id))
                return None
        else:
            _debug(2,'No pagenr or section known for article %s' % self.id)
            return None


    @property
    def source(self):
        if self.medium:
            return self.db.sources.lookupID(self.medium)
        
    def getSourceName(self):
        """
        Looks up the medium (source id) and returns the name
        """
        if self.medium:
            return self.source.name

    def __str__(self):
        return ('<article id="%(id)s" date="%(date)s" source="%(medium)s" length="%(length)s">' +
                '\n  <headline>%(headline)s</headline>\n</article>') % self.__dict__

    def fulltext(self):
        #if self.type == 4:
        #    result = self.text # (parsed headline is included in text)
        #    if self.text:
        #        result = result.replace("\\r/N(soort,ev,neut)/\\r","")
        #    else:
        #        #toolkit.warn("No text for article %s?" % self.id)
        #        return None
        #else:
        result = (self.headline or '') +"\n\n"+ (self.byline or "")+"\n\n"+(self.text or "")
        return result.replace("\\r","").replace("\r","\n")

    def splitSentences(self):
        text = self.text
        if not text:
            text = ""
        text = re.sub(r"q11\s*\n", "\n\n",text)
        if self.headline: text = self.headline.replace(";",".")+ "\n\n" + text
        spl = sbd.splitPars(text)
        for parnr, par in izip(count(1), spl):
            for sentnr, sent in izip(count(1), par):
                s = Sentence(self, None, parnr, sentnr,  sentence=sent)
                yield s

    def words(self, onlyWords = False, lemma=0): #lemma: 1=lemmaP, 2=lemma, 3=word
        text = self.text
        if not text: return []
        text = toolkit.stripAccents(text)
        text = text.encode('ascii', 'replace')
        text = ctokenizer.tokenize(text)
        #toolkit.warn("Yielding words for %i : %s" % (self.id, text and len(text) or `text`))
        text = re.sub("\s+", " ", text)
        return words(text, onlyWords, lemma)

    def uploadimage(self, *args, **kargs):
        self.db.uploadimage(self.id, *args, **kargs)

    def getImages(self):
        """
        returns the images belonging to self article (if any)
        """
        SQL = "SELECT ai.sentenceid, length, breadth, abovefold, imgType FROM articles_images ai inner join sentences s on ai.sentenceid=s.sentenceid WHERE articleid=%i" % self.id
        return [Image(self, getCapt=True, *data) for data in self.db.doQuery(SQL)]

    def getSentences(self):
        return self.sentences

    @property
    @cached
    def sentences(self):
        data = self.db.doQuery("select sentenceid, parnr, sentnr from sentences where articleid=%i order by parnr, sentnr" % self.id)
        if data:
            return [Sentence(self, *row) for row in data]
        else:
            sents = list(self.splitSentences())
            return sents

    def getLink(self):
        return "articleDetails?articleid=%i" % self.id

    def getWeekNr(self): return toolkit.getYW(self.date)

    def __id__(self):
        return self.id

    def __del__(self):
        if toolkit:
            toolkit.delCachedProp(self, "sentences")

    def __eq__(self, other):
        return isinstance(other, Article) and other.id == self.id
    def __hash__(self):
        return hash(type(self)) ^ hash(self.id) 

    def storeImage(self, imgdata, format):
        SQL = "DELETE FROM articles_image WHERE articleid=%i" % (self.id,)
        self.db.doQuery(SQL)
        imgdata = binascii.hexlify(imgdata)
        SQL = "INSERT INTO articles_image VALUES (%i, 0x%s, %s)" % (self.id, imgdata, dbtoolkit.quotesql(format))
        self.db.doQuery(SQL)

    def getImage(self):
        SQL = "SELECT image, datalength(image), format FROM articles_image WHERE articleid=%i" % self.id
        data = self.db.doQuery(SQL)
        if not data: return None, None
        bytes2, l, format = data[0]
        while l > len(bytes2):
            SQL = "SELECT substring(image, %i, 8000) from articles_image WHERE articleid=%i" % (len(bytes2)+1, self.id)
            bytes2 += self.db.doQuery(SQL)[0][0]
        return bytes2, format

    def quote(self, words_or_wordfilter, **kargs):
        return quote(list(self.words()), words_or_wordfilter, **kargs)
    
def quote(words, words_or_wordfilter, quotelen=4, totalwords=25, boldfunc = lambda w : "<b>%s</b>" % w):
    if callable(words_or_wordfilter):
        filt = words_or_wordfilter
    else:
        filt = lambda x: int(x in words_or_wordfilter)
        
    positions = {}
    for i, w in enumerate(words):
        if filt(w):
            positions[i] = 0
    for pos in sorted(positions.keys()):
        nbs = 0
        for w in positions:
            dist = abs(w - pos)
            nbs += int(dist > 0 and dist <= quotelen)
        positions[pos] = nbs
    
    quotewords = set() # wordids
    boldwords = set()
    while len(quotewords) < totalwords:
        pos, nbs = toolkit.sortByValue(positions, reverse=True)[0]
        boldwords.add(pos)
        quote = range(max(0, pos - quotelen), min(len(words), pos + quotelen + 1))
        quotewords |= set(quote)
        del positions[pos]
        if not positions: break
    if not quotewords: return None
    lag = -1
    result = []
    quotewords = sorted(quotewords)
    for i in quotewords:
        if i > lag+1: result += ["..."]
        result += [boldfunc(words[i])] if (i in boldwords and boldfunc) else [words[i]]
        lag = i
    if quotewords[-1] <> len(words) - 1:
        result += ["..."]
    
    return " ".join(result)

        

def encodeAndLimitLength(variables, lengths):
    originals = map(lambda x: x and x.strip(), variables)
    numchars = 5
    while True:
        variables, enc = dbtoolkit.encodeTexts(variables)
        done = True
        for i, (var, maxlen, original) in enumerate(zip(variables, lengths, originals)):
            if var and (len(var) > maxlen):
                done = False
                variables[i] = original[:maxlen-numchars] + " ..."
        if done: return variables, enc
        numchars += 5
                
        

def createArticle(db, headline, date, source, batchid, text, texttype=2,
                  length=None, byline=None, section=None, pagenr=None, fullmeta=None, url=None, externalid=None, retrieveArticle=1):
    """
    Writes the article object to the database
    """

    if toolkit.isDate(date): date = toolkit.writeDateTime(date, 1)
    if type(source) == sources.Source: source = source.id
    if type(fullmeta) == dict: fullmeta = `fullmeta`

    if url and len(url) > 490: url = url[:490] + "..."

    (headline, byline, fullmeta, section), encoding = encodeAndLimitLength([headline, byline, fullmeta, section], [740, 999999, 999999, 90])
    
    if pagenr and type(pagenr) in (types.StringTypes): pagenr = pagenr.strip()
    if text: text = text.strip()
    if length == None and text: length = len(text.split())

    
    q = {'date' : date,
         'length' : length,
         'metastring' : fullmeta,
         'headline' : headline,
         'byline' : byline,
         'section' : section,
         'pagenr': pagenr,
         'batchid' : batchid,
         'mediumid' : source,
         'url':url,
         'externalid':externalid,
         'encoding' : encoding}
    aid = db.insert('articles', q)

    text, encoding = dbtoolkit.encodeText(text)
    
    q = {'articleid' : aid,
         'type' : texttype,
         'encoding' : encoding,
         'text' : text}
    
    db.insert('texts', q, retrieveIdent=0)
    
    if retrieveArticle:
        return fromDB(db, aid)



def words(text, onlyWords=False, lemma=0): #lemma: 1=lemmaP, 2=lemma,3 =word
    for w in text.split(" "):
        if not w: continue
        if lemma==1: w= toolkit.wplToWc(w)
        elif lemma==2: w= w.split("/")[-1]
        elif lemma==3: w= w.split("/")[0]
        if (not onlyWords) or w.isalpha():#re.search("\w", w):
            yield w

'''
def fromXML2(str):
    import xml.dom.minidom
    articles = []
    doc = xml.dom.minidom.parseString(str)
    for art in doc.getElementsByTagName("article"):
        
        id       = int(toolkit.xmlElementText(art, "dc:identifier"))
        headline = toolkit.xmlElementText(art, "dc:title")
        print toolkit.xmlElementText(art, "publisherid")
        mediumid = int(toolkit.xmlElementText(art, "publisherid"))
        date     = toolkit.readDate(toolkit.xmlElementText(art, "dc:date"))
        text     = toolkit.xmlElementText(art, "content")
        
        a = Article(None, id, None, mediumid, date, headline, None, None, None, None, None,text, type=4)
        articles.append(a)

    return articles
'''

def fromDB(db, id):
    try:
        return list(articlesFromDB(db,(id,)))[0]
    except IndexError:
        raise Exception('articleid %r not found' % id)

        
def articlesFromDB(db, ids, headline=True):
    """
    Article Factory method to create an article from the database
    """
    if not ids:
        return 
    if not db:
        db = dbtoolkit.anokoDB()
    data = None; text = None
    if toolkit.isSequence(ids, True):
        ids = ",".join(str(id) for id in ids)
        
    sql = """SELECT articleid, batchid, mediumid, date, headline, length, pagenr, encoding
             FROM articles WHERE articleid in (%s)""" % ids
    for d in db.doQuery(sql):
        yield Article(db,*d)

def articleExistsInDB(db,batchid,url):
    if not db:
        db = dbtoolkit.anokoDB()
    if not batchid:
        raise Exception('batchid not given')

    sql = """SELECT articleid FROM articles WHERE url = '%s' AND batchid=%s""" % (url, batchid)
    result = db.doQuery(sql)
    return result


CACHE_SIZE = 200
def Articles(aidlist, db, tick=False):
    """
    Generator that yields articles using caching to minimize db roundtrips
    """
    aidlist = list(aidlist)
    if tick: toolkit.ticker.warn("Iterating over articles", estimate = len(aidlist))
    for aid in iter(aidlist):
        toolkit.ticker.tick()
        cache = articlesFromDB(db, aidlist[:CACHE_SIZE])
        for a in cache:
            yield a
        aidlist = aidlist[CACHE_SIZE:]

        
        
        
class Image:
    def __init__(self, article, sentid, length, breadth, abovefold, typ, caption=None, getCapt=False):
        self.article = article
        self.sentid = int(sentid)
        self.length = int(length)
        self.breadth = int(breadth)
        self.abovefold = bool(abovefold)
        self.typ = typ
        self.caption = caption
        if getCapt:
            self.caption = getCaption(self.article.db, sentid)

def getCaption(db, sentid):
    aid, parnr = db.doQuery("SELECT articleid, parnr FROM sentences WHERE sentenceid=%i"%sentid)[0]
    data = db.doQuery("SELECT sentence FROM sentences WHERE articleid=%i AND parnr=%i AND sentnr=2" % (aid, parnr))
    if data:
        return data[0][0]
    else:
        return None
                      
'''
def fromXML2(str):
    import xml.dom.minidom
    articles = []
    str = str.replace("&","+")
    doc = xml.dom.minidom.parseString(str)
    for art in doc.getElementsByTagName("article"):
        
        id       = int(toolkit.xmlElementText(art, "dc:identifier"))
        headline = toolkit.xmlElementText(art, "dc:title")
        mediumid = int(toolkit.xmlElementText(art, "publisherid"))
        date     = None#toolkit.readDate(toolkit.xmlElementText(art, "dc:date"))
        text     = toolkit.xmlElementText(art, "content")
        
        a = Article(None, id, None, mediumid, date, headline, None, None, None, None, None,text, type=4)
        articles.append(a)

    return articles
    '''


def splitArticles(aids, db, tv=False):
    from itertools import izip, count
    error = ''
    for article in Articles(aids, db, tick=True):
        if db.doQuery("SELECT TOP 1 articleid FROM sentences WHERE articleid = %s and parnr >= 0" % article.id):
            #toolkit.warn("Article %s already split, skipping!" % article.id)
            continue
        text = article.text
        if not text:
            toolkit.warn("Article %s empty, adding headline only" % article.id)
            text = ""
        text = re.sub(r"q11\s*\n", "\n\n",text)
        #if article.byline: text = article.byline + "\n\n" + text
        if article.headline: text = article.headline.replace(";",".")+ "\n\n" + text
        spl = sbd.splitPars(text)
        for parnr, par in izip(count(1), spl):
            for sentnr, sent in izip(count(1), par):
                #return `{"articleid":article.id, "parnr" : parnr, "sentnr" : sentnr, "sentence" : sent.strip()[:7000]}`
                sent = sent.strip()
                orig = sent
                [sent], encoding = dbtoolkit.encodeTexts([sent])
                if len(sent) > 450:
                    longsent = orig
                    sent = orig[:50] + '[...]'
                    [sent, longsent], encoding = dbtoolkit.encodeTexts([sent, longsent])
                else:
                    longsent = None

                try:
                    db.insert("sentences", {"articleid":article.id, "parnr" : parnr, "sentnr" : sentnr, "sentence" : sent, 'longsentence': longsent, 'encoding': encoding})
                except Exception, e:
                    error += '%s: %s\n' % (article.id , e)
        toolkit.warn("Parsed article %i"% article.id)
        db.conn.commit()
    return error
    

class Sentence(object):
    def __init__(self, article, sid, parnr, sentnr, sentence = None):
        self.sid = sid
        self.parnr = parnr
        self.sentnr = sentnr
        self._article = weakref.ref(article)
        self._sentence = sentence
    def getSentence(self):
        return self.text

    def __id__(self):
        if self.sid:
            return self.sid
        else:
            return "%s:%s:%s" % (self.article.id, self.parnr, self.sentnr)

    @property
    def article(self):
        a = self._article()
        if a is None: raise Exception("Article already finalized!")
        return a

    @property
    @cached
    def text(self):
        if self._sentence: return self._sentence
        db = self.article.db
        try:
            text, enc = db.doQuery("select isnull(longsentence,sentence), encoding from sentences where sentenceid = %i" % self.sid)[0]
            if enc: return dbtoolkit.decode(text, enc)
            else: return text.decode('ascii', 'replace')
        except Exception, e:
            if "could not be converted" in str(e):
                _debug(1, 'Encoding problem in sentence nr %i'  % (self.sid))
                return "?????" 
            raise e

    def getLink(self):
        return 'sentenceDetails?sentenceid=%d' % self.sid
    
    def __str__(self):
        return "(%i, %i)" % (self.parnr, self.sentnr)
    def __repr__(self):
        return "Sentence(%r, %i, %i, %i)" % (self.article, self.sid, self.parnr, self.sentnr)
    def __cmp__(self, other):
        c = cmp(self.parnr, other.parnr)
        if not c: c = cmp(self.sentnr, other.sentnr)
        return c
        

def sentFromDB(db, sid):
    data = db.doQuery("select sentenceid, parnr, sentnr, articleid from sentences where sentenceid=%i" % sid)
    if not data: return None
    sid, parnr, sentnr, aid = data[0]
    a = fromDB(db,aid)
    return Sentence(sid, parnr, sentnr, a)
    

if __name__ == '__main__':
    import dbtoolkit
    a = fromDB(dbtoolkit.amcatDB(), 44133956)
    print a.quote(["yakult"], boldfunc=None)

    
