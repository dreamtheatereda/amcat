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
Rules for extraction statements from semantic roles
"""

import collections, csv

PREDICATE_RELATIONS = "vc",

class Statement(object):
    def __init__(self, subject, predicate, object, source=None, type=None, condition=None):
        self.subject = frozenset(subject)
        self.predicate = frozenset(predicate)
        self.object = frozenset(object)
        self.source = frozenset(source) if source is not None else frozenset()
        self.condition = frozenset(condition) if condition is not None else frozenset()
        self.type = frozenset(type) if type is not None else frozenset()

    def get_lemmata(self, position):
        return ",".join("%s/%s" % (t.word.lemma.lemma, t.word.lemma.pos)
                        for t in getattr(self, position) if t is not None)
    
    def add_type(self, type):
        self.type |= frozenset([type])
    def __key(self):
        return (self.subject, self.predicate, self.object, self.source, self.condition, self.type)
    def __eq__(x, y):
        return x.__key() == y.__key()
    def __hash__(self):
        return hash(self.__key())
    def __str__(self):
        s = lambda nodes : ",".join(map(str, nodes))
        typestr = " (%s)" % s(self.type) if self.type else ""
        condstr = " (IF %s)" % s(self.condition) if self.condition else ""
        result = "%s/%s%s%s/%s" % (s(self.subject), s(self.predicate), typestr, condstr, s(self.object))
        if self.source:
            result = "%s:%s" % (s(self.source), result)
        return result
    __repr__ = __str__

def get_predicates(sentence):
    """
    Determine the predicates given a set of co-membership relations
    Input: A analysed_sentence
    Output: a dict of node : predicate, where predicate is a set of nodes (shared between predicates
            such that if a and b are in the same predicate, predicates[a] is predicates[b] and
            {a,b} - predicate[b] is the empty set.
    """
    predicates = {} # node -> set(nodes) # set of sets
    for t in sentence.triples:
        if t.relation.label in PREDICATE_RELATIONS:
            combined = frozenset(predicates.get(t.child, set([sentence.get_token(t.child.position)]))
                                 | predicates.get(t.parent, set([sentence.get_token(t.parent.position)])))
            for node in t.child, t.parent:
                predicates[node] = combined
    return predicates

def get_statements(sentence, roles):
        
    predicates = get_predicates(sentence)
    # relations per predicate: {predicate : {rel : {nodes}}}
    rels_per_predicate = collections.defaultdict(lambda : collections.defaultdict(set))
    for subject, role, object in roles:
        subject = sentence.tokendict[subject] if subject is not None else None
        object = sentence.tokendict[object]
        pred = predicates.get(object, frozenset([object]))
        if role in ("su", "obj", "quote"): # node -> predicate
            rels_per_predicate[pred][role].add(subject)
        elif role == "om": # means_predicate -> goal_predicate
            means = predicates.get(subject, frozenset([subject]))
            rels_per_predicate[pred][role].add(means)

    # normal statement: if a su and obj point to the same predicate, it is a statement
    for pred, rels in rels_per_predicate.items():
        if "obj" in rels and "su" in rels:
            s = Statement(rels["su"], pred, rels["obj"], rels["quote"])
            if rels["su"] == frozenset([None]): s.add_type("Reality")
            yield s
        elif "obj" in rels and "om" in rels:
            for means_predicate in rels["om"]:
                means_rels = rels_per_predicate[means_predicate]

                # S says that X does Y in order to increase Z
                # so, X wants to increase Z (according to S)
                yield Statement(means_rels["su"], pred, rels["obj"],
                                source=means_rels["quote"], type={"Affective"})
                # and, X thinks that doing Y will increate Z
                yield Statement(means_rels["obj"], pred, rels["obj"],
                                source=(means_rels["quote"] | means_rels["su"]),
                                condition=means_predicate,
                                type={"Causal"})
            
                
    
    
###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest


class TestStatementExtraction(amcattest.PolicyTestCase):

    def test_predicates(self):
        from amcat.models import Triple, Relation
        s = amcattest.create_test_analysis_sentence()
        #jan moest piet slaan
        jan, wilde, piet, slaan = [amcattest.create_test_token(sentence=s, position=i) for i in range(1,5)]
        for child, parent, rel in [(jan, moest, "su"),
                                   (jan, slaan, "su"),
                                   (moest, slaan, "vc"),
                                   (piet, slaan, "obj1")]:
            rel = Relation.objects.create(label=rel)
            Triple.objects.create(parent=parent, child=child, relation=rel)

        preds = get_predicates(s)
        self.assertEqual(preds, {moest : {moest, slaan},
                                 slaan : {moest, slaan}})

        
    def test_statements(self):
        # jan moest piet slaan, volgens kees, om marie te helpen
        from amcat.models import Triple, Relation
        s = amcattest.create_test_analysis_sentence()
        jan, moest, piet, slaan, volgens, kees, omte, marie, helpen = [
            amcattest.create_test_token(sentence=s, position=i) for i in range(1,10)]
        for child, parent, rel in [(jan, moest, "su"),
                                   (jan, slaan, "su"),
                                   (moest, slaan, "vc"),
                                   (piet, slaan, "obj1"),
                                   (volgens, slaan, "mod"),
                                   (kees, volgens, "obj1"),
                                   (omte, slaan, "om"),
                                   (helpen, omte, "body"),
                                   (marie, helpen, "obj1"),
                                   ]: 
            rel = Relation.objects.create(label=rel)
            Triple.objects.create(parent=parent, child=child, relation=rel)

        roles = ((jan.position, "su", slaan.position),
                 (piet.position, "obj", slaan.position),
                 (kees.position, "quote", moest.position))

        direct = {Statement({jan}, {moest, slaan}, {piet}, source={kees})}
        
        statements = set(get_statements(s, roles))
        self.assertEqual(statements, direct)

        
        # om marie te helpen
        roles += ((marie.position, "obj", helpen.position), )
        
        statements = set(get_statements(s, roles))
        self.assertEqual(statements, direct)

        roles += ((moest.position, "om", helpen.position), )


        om = {Statement({jan}, {helpen}, {marie}, type={"Affective"}, source={kees}),
              Statement({piet}, {helpen}, {marie}, source={jan, kees},
                        condition={moest, slaan}, type={"Causal"}),
              }
        

        
        statements = set(get_statements(s, roles))
        self.assertEqual(statements, direct | om)

    def test_reality(self):
        from amcat.models import Triple, Relation
        s = amcattest.create_test_analysis_sentence()
        # VVD stijgt (dwz in de peilingen)
        vvd, stijgt = [
            amcattest.create_test_token(sentence=s, position=i) for i in range(1,3)]

        for child, parent, rel in [(vvd, stijgt, "su")]:
            rel = Relation.objects.create(label=rel)
            Triple.objects.create(parent=parent, child=child, relation=rel)
            

        roles = ((None, "su", stijgt.position),
                 (vvd.position, "obj", stijgt.position))

        
        rea = {Statement({None}, {stijgt}, {vvd}, type={"Reality"})}
        
        statements = set(get_statements(s, roles))
        self.assertEqual(statements, rea)

    def test_nqueries(self):
        from amcat.models import Triple, Relation
        s = amcattest.create_test_analysis_sentence()
        jan, moest, piet, slaan, volgens, kees, omte, marie, helpen = [
            amcattest.create_test_token(sentence=s, position=i) for i in range(1,10)]
        with self.checkMaxQueries(1):
            s._get_tokens(get_words=True)

        for child, parent, rel in [(jan, moest, "su"),
                                   (jan, slaan, "su"),
                                   (moest, slaan, "vc"),
                                   (piet, slaan, "obj1"),
                                   (volgens, slaan, "mod"),
                                   (kees, volgens, "obj1"),
                                   (omte, slaan, "om"),
                                   (helpen, omte, "body"),
                                   (marie, helpen, "obj1"),
                                   ]: 
            rel = Relation.objects.create(label=rel)
            Triple.objects.create(parent=parent, child=child, relation=rel)

            roles = ((jan.position, "su", slaan.position),
                     (piet.position, "obj", slaan.position),
                     (kees.position, "quote", moest.position))

        from amcat.tools.djangotoolkit import list_queries
            
        with self.checkMaxQueries(1):
            statements = set(get_statements(s, roles))
            
        with self.checkMaxQueries(0):
            s = str(statements)



