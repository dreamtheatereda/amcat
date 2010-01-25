import toolkit, dbtoolkit, re, project, sources, types
from itertools import izip, count
from functools import partial
_debug = toolkit.Debug('article',1)
from cachable import Cachable, DBPropertyFactory, DBFKPropertyFactory

def doCreateArticle(db, aid, **cache):
    return Article(db, aid, **cache)

import sentence
    
class Article(Cachable):
    """
    Class representing a newspaper article
    """
    __table__ = 'articles'
    __idcolumn__ = 'articleid'
    __labelprop__ = 'headline'
    __encodingprop__ = 'encoding'
    __dbproperties__ = ["date", "length", "pagenr", "url", "encoding"]
    headline = DBPropertyFactory(decode=True)
    byline = DBPropertyFactory(decode=True)
    metastring = DBPropertyFactory(decode=True)
    section = DBPropertyFactory(decode=True)
    text = DBPropertyFactory(table="texts", decode=True)
    batch = DBPropertyFactory("batchid", dbfunc=lambda db, id: project.Batch(db, id))
    source = DBPropertyFactory("mediumid", dbfunc=sources.Source)
    sentences = DBFKPropertyFactory("sentences", "sentenceid", dbfunc=sentence.Sentence)

    @property
    def fullmeta(self):
        return toolkit.dictFromStr(self.metastring)
    @property
    def project(self):
        return self.batch.project

    def fulltext(self):
        result = (self.headline or '') +"\n\n"+ (self.byline or "")+"\n\n"+(self.text or "")
        return result.replace("\\r","").replace("\r","\n")

    def words(self, onlyWords = False, lemma=0): #lemma: 1=lemmaP, 2=lemma, 3=word
        import ctokenizer
        text = self.text
        if not text: return []
        text = toolkit.stripAccents(text)
        text = text.encode('ascii', 'replace')
        text = ctokenizer.tokenize(text)
        #toolkit.warn("Yielding words for %i : %s" % (self.id, text and len(text) or `text`))
        text = re.sub("\s+", " ", text)
        return text.split(" ")

    def quote(self, words_or_wordfilter, **kargs):
        return toolkit.quote(list(self.words()), words_or_wordfilter, **kargs)

def Articles(aids, db):
    return [Article(db, aid) for aid in aids]

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

if __name__ == '__main__':
    import dbtoolkit
    a = Article(dbtoolkit.amcatDB(), 33308863)
    print a.quote(["de"])
