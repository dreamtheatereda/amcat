import dbtoolkit, analysis
import amcattest

class AnalysisTest(amcattest.AmcatTestCase):

    def testAnalysis(self):
        a = analysis.Analysis(self.db, 2)
        self.assertEqual(a.label, "Alpino")
        self.assertEqual(a.language.id, 2)

    def testGetAll(self):
        a = analysis.Analysis(self.db, 2)
        self.assertIn(a, analysis.Analysis.getAll(self.db))

if __name__ == '__main__':
    amcattest.main()

