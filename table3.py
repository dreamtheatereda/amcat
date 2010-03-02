"""
Interface and base implmentations for a generic table type

Interface Table:
  getColumns(): returns a sequence of objects that represent columns
  getRows():    returns a sequence of objects that represent rows
  getValue(row, column): returns an object representing a value given
                         two objects from getRows()/getColumns()

see tableoutput.py for useful methods for rendering tables in different ways
"""

import toolkit, types
from toolkit import isnull
from oset import OrderedSet
def trivialCellFunc(row, col): return "%s/%s" % (row, col)

class Table(object):
    def __init__(self, columns=None, rows = None, cellfunc = trivialCellFunc):
        """
        columns and rows can be given or omitted if getColumns/getRows is overridden (default [])
        cellfunc can be given as (row,col)->value, or omitted if gteValue is overridden (default: trivialcellfunc)
        """
        self.columns    = isnull(columns, []) 
        self.rows       = isnull(rows, [])
        self.cellfunc   = cellfunc            
    def getValue(self, row, column):
        return self.cellfunc(row, column)
    def getRows(self):
        return self.rows
    def getColumns(self):
        return self.columns

class ObjectColumn(object):
    def __init__(self, cellfunc):
        self.cell = cellfunc
    def getCell(self, row):
        return self.cellfunc(row)
    
class ObjectTable(Table):
    """
    Convenience subclass of Table that assumes the rows contain
    a domain object and the columns are properties of those objects
    The colunms should be ObjectColunms or some other object
    that has a getCell(row) -> value function
    """
    def __init__(self, rows = None, columns = None):
        self.rows = rows or []
        self.columns = columns or []
        self.cellfunc = lambda row, col : col.getCell(row)
    def addColumn(self, col):
        if type(col) == types.FunctionType:
            col = ObjectColumn(col)
        self.columns.append(col)

class DictTable(Table):
    """
    Convenience subclass of Table that creates a dict to hold the cell values,
    and adds column and row objects as needed
    """
    def __init__(self, default=None):
        Table.__init__(self, OrderedSet(), OrderedSet(),
                       self.getValue)
        self.data = {}
        self.default = default
    def addValue(self,row, col, value):
        self.data[row, col] = value
        self.columns.add(col)
        self.rows.add(row)
    def getValue(self, row, col):
        return self.data.get((row, col), self.default)
    def __getstate__(self):
        d = self.__dict__
        if d['cellfunc'] == self.getValue: del d['cellfunc']
        return d
    def __setstate__(self, d):
        if 'cellfunc' not in d: d['cellfunc'] = self.getValue
        self.__dict__ = d
    
DataTable = DictTable

class ListTable(Table):
    """
    Convenience subclass of Table that is based on a list-of-lists
    such as output by dbapi::cursor.fetchall()
    if colnames is not given, len(rows[0]) is used to determine #columns, causing an error
       if the data is not subscriptable
    """
    def __init__(self, data=None, colnames=None):
        Table.__init__(self, rows=data or [])
        self.colnames = colnames
    def getColumns(self):
        if not self.rows: return []
        colnames = self.colnames or range(len(toolkit.head(self.rows)))
        return [toolkit.IDLabel(i, colname) for (i, colname) in enumerate(colnames)]
    def addRow(self, *row):
        self.rows.append(row)
    def getValue(self, row, col):
        if col.id >= len(row): return None
        return row[col.id]

class SortedTable(Table):
    """
    Encapsulated another table object and "jit"-sorts rows as needed
    sort can be a columns, a (column, bool) pair, or a list of columns or pairs
    addsortindicator only works if columns are IDLabels
    """
    def __init__(self, table, sort):
        Table.__init__(self, cellfunc = table.getValue)
        self.table = table
        self.sort = []
        if not toolkit.isSequence(sort, excludeStrings=True) or (len(sort) == 2 and type(sort[1]) == bool):
            sort = [sort]
        for col in sort:
            if toolkit.isSequence(col): self.sort.append((col[0], col[1]))
            else: self.sort.append((col, True))
    def getColumns(self):
        return self.table.getColumns()
    def cmp(self, a, b):
        for col, asc in self.sort:
            ab = [self.getValue(x, col) for x in (a,b)]
            return cmp(*ab) * (1 if asc else -1)
        return 0
    def getRows(self):
        return sorted(self.table.getRows(), cmp=self.cmp)

class MergedTable(Table):
    """
    Encapsulates two table objects, displaying columns side-by-side
    """
    def __init__(self, *tables):
        """
        tables can be any number of Table objects
        """
        self.tables = list(tables)
        self.columnfilter = lambda t, c: True # table, column -> bool
    def getColumns(self):
        result = []
        for table in self.tables:
            result += [toolkit.IDLabel((table, c), c)
                       for c in table.getColumns()
                       if self.columnfilter(table, c)]
        return result
    def getRows(self):
        # Iterators would be good here!
        rowss = [t.getRows() for t in self.tables]
        for i in range(max(map(len, rowss))):
            row = []
            for rows in rowss:
                if len(rows) <= i: row.append(None)
                else: row.append(rows[i])
            yield row
    def getValue(self, row, col):
        table, col = col.id
        row = row[self.tables.index(table)]
        if not row: return None
        return table.getValue(row, col)
    
def getColumnByLabel(table, label):
    stringify = unicode if type(label) == unicode else str
    for c in table.getColumns():
        if stringify(c) == label: return c

            
        
if __name__ == '__main__':
    import tableoutput
    t = ListTable(colnames = ["a1", "a2", "a3"],
                  data = [[1,2,3],
                          [7,8,9],
                          [4,5,6],
                          ])
 
    print tableoutput.table2ascii(t)

    s = SortedTable(t, getColumnByLabel(t, "a2"))
    print tableoutput.table2ascii(s)
    
    t2 = ListTable(colnames = ["b1", "b2"],
                   data = [['a','A'],
                           ['c','C'],
                           ['d','D'],
                           ['b','B'],
                           ])
    
    print tableoutput.table2ascii(t2)
    m = MergedTable(t, t2)
    m.columnfilter = lambda tab,col : col.label <> "a1"
    print tableoutput.table2ascii(m)

    l = getColumnByLabel(m, "b1")
    print l
    s = SortedTable(m, getColumnByLabel(m, "b1")) 
    print tableoutput.table2ascii(s)

