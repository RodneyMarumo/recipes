import numpy as np
from myio import warn
from .string import SuperString, as_superstrings
from .misc import getTerminalSize
from .iter import as_sequence, first_true_index

from IPython import embed

##########################################################################################################################################   
#from PyQt4.QtCore import pyqtRemoveInputHook, pyqtRestoreInputHook
#TODO:  Check out astropy.table ...........................
#TODO: HIGHLIGHT ROWS / COLUMNS
class Table( object ):

    ALLOWED_KWARGS = [] #TODO
    #====================================================================================================
    def __init__(self, data, title=None, title_props=(),
                    col_headers=None, col_head_props='bold', col_widths=None, col_borders='|', col_sort=None,
                    row_headers=None, row_head_props='bold', where_row_borders=None, row_sort=None,
                    align='left', num_prec=2, enumera=False,
                    ignore_keys=None  ):
        '''
        Class to create and optionally colourise tabular representation of data for terminal output.
        Parameters
        ----------
        data            :       input data - must be 1D, 2D or dict
                                if dict, keys will be used as row_headers, and values as data
        title           :       The table title
        title_props     :       str, tuple or dict with ANSICodes property descriptors
        
        col_headers     :       column headers.
        col_head_props  :       str, tuple or dict with ANSICodes property descriptors to use as global column header properties
                                TODO: OR a sequence of these, one for each column
        col_widths      :       numerical column width
        col_borders     :       character used as column seperator
        col_sort        :       TODO callable that operates on strings and returns column sorting order
        
        row_headers     :
        row_head_props  :       see col_head_props
        where_row_borders:      sequence with row numbers below which a solid border will be drawn.  
                                Default is after column headers and after last line
        row_sort        :       TODO callable that operates on strings and returns row sorting order
        
        align           :       column alignment - ('left', 'right', or 'center')
        num_prec        :       integer precision to use for number representation FIXME!!!!!!!!!!!!!
        enumera         :       bool
            Will number the rows if True
        
        ignore_keys     :       if dictionary is passed as data, optionally specify the keys that will not be printed in table 
        '''
        
        #self.datatypes = np.vectorize(type)(data)
        self.original_data = data
        
        if isinstance(data, dict):
            if not row_headers is None:
                warn( "Dictionary keys will be superceded by 'row_headers'." )
            row_headers, data = self.convert_dict( data, ignore_keys )
        
        #convert to array of SuperStrings
        self.data = as_superstrings( data )
        
        #check data shape
        dim = np.ndim(self.data)
        if dim == 1:
            self.data = self.data[None].T               #default for 1D data is to display in a column with row_headers
        if dim > 2:
            raise ValueError( 'Only 2D data can be tabelised!  Data is {}D'.format(dim) )
        
        #title
        self.title = title
        self.title_props =  title_props
        
        self.enumera = enumera
        
        #row and column headers
        self.has_row_head = not row_headers is None
        self.has_col_head = not col_headers is None
        
        if self.has_col_head:
            self.col_headers = self.apply_props(col_headers, col_head_props)
        if self.has_col_head and self.has_row_head:
            #TODO:  when both are given, the 0,0 table position is ambiguously both column and row header
            #TODO:  allow user to specify either
            if len(row_headers) == self.data.shape[0]:
                row_headers = [''] + list(row_headers)
        if self.has_row_head:
            Nrows = len(row_headers)
            self.row_headers = self.apply_props(row_headers, row_head_props).reshape(Nrows,1)
        
        self.pre_table = self.add_headers()
        Nrows, Ncols = self.pre_table.shape
        
        #Column specs
        if col_widths is None:
            self.col_widths = np.vectorize(len)( self.pre_table ).max(axis=0) + 1
            self.col_widths_no_ansi = np.vectorize(SuperString.len_no_ansi)( self.pre_table ).max(axis=0) + 1
        else:
            self.col_widths = col_widths
        
        self.col_borders = col_borders
        
        #column alignment
        almap = { 'r' : '>', 'l' : '<', 'c' : '^' }     #map to alignment characters
        if align.lower()[0] in almap:
            self.align = almap[ align.lower()[0] ]
        else:
            raise ValueError( 'Unrecognised alignment {!r}'.format(align) )
        
        #The column format specification. 0 - item; 1 - fill; 2 - alignment character
        self.col_fmt = '{0:{2}{1}}'     
        self.num_prec = num_prec
        
        #Row specs
        self.rows = []
        self.row_fmt = ('{}'+self.col_borders) * Ncols
        
        if where_row_borders:
            self.where_row_borders = where_row_borders
        else:
            if self.has_col_head:
                self.where_row_borders = [0, Nrows-1]
            else:
                self.where_row_borders = [Nrows-1]
    
    #====================================================================================================
    def __repr__( self ):
        if len(self.original_data):
            self.make_table( )
            return '\n'.join( self.table )
        else:
            return '|Empty Table|'
        
    #====================================================================================================    
    def __str__( self ):
        return repr(self)
    
    #====================================================================================================    
    @staticmethod
    def apply_props( obj, props=() ):
        if isinstance(props, dict):
            return as_superstrings(obj, **props)
        else:
            props = as_sequence( props, return_as=tuple)
            return as_superstrings(obj, *props)
    
    #====================================================================================================    
    def convert_dict(self, dic, ignore_keys):
        _dic = dic.copy()
        if not ignore_keys is None:
            ignore = [_dic.pop(key) for key in ignore_keys if key in _dic]
        
        keys = list(_dic.keys())
        vals = list(_dic.values())
        return keys, vals
    
    #====================================================================================================    
    def add_headers( self ):
        
        data = self.data[...]

        if self.has_col_head:
            data = np.vstack( (self.col_headers, data) )

        if self.has_row_head:
            data = np.hstack( (self.row_headers, data) )
            
        if self.enumera:
            numbers = np.arange(1, data.shape[0]+1).astype(str)
            if self.has_col_head:
                numbers = ['#'] + list(numbers[:-1])
            
            data = np.c_[numbers, data]
        
        return as_superstrings(data)    #as_superstrings necessary because numpy sometimes implicitly converts SuperStrings to str
    
    #====================================================================================================
    def create_row(self, columns):
        '''apply properties each item in the list of columns create a single string'''
        al = self.align
        columns = as_superstrings( columns )
        col_padwidths =  [ w+col.ansi_len() if col.has_ansi() else w 
                                for col,w in zip(columns, self.col_widths_no_ansi) ]
        columns = [self.col_fmt.format(col, cw, al) for col,cw in zip(columns, col_padwidths)]     #this is needed because the alignment formatting gets screwed up by the ANSI characters that have length, but are not displayed
        row = self.col_borders + self.row_fmt.format(*columns)
        row = SuperString(row)
        self.rows.append( row )
        
        return row
    
    #====================================================================================================
    def colourise(self, states, *colours):
        
        #if less colours than number of states are specified
        if len(colours) < states.max()+1:
            colours = ('default',) + colours            #i.e. index zero corresponds to default colour
        
        while len(colours) < states.max()+1:
            colours += colours[-1:]                     #all remaining higher states will be assigned the same colour
        
        embed()
        for i,c in enumerate(colours):
            where = states==i
            if np.any(where):
                cdata = as_superstrings( self.data[where], c )
                self.data[where] = cdata
        
        self.pre_table = self.add_headers()
        return self.data
    
    #====================================================================================================
    def make_table( self, truncate=0 ):
        #Express data table as SuperString
        from copy import copy
        table = []
        lcb = len(self.col_borders)
        table_width = sum(self.col_widths_no_ansi+lcb) + lcb
        use_width = copy(table_width)
        trunc = lambda row : row
        
        if truncate:
            #FIXME!
            termW,termH = getTerminalSize()
        
            if table_width > termW:
                use_width = termW
            
                cs = np.cumsum(self.col_widths_no_ansi)
                iq = first_true_index( cs > termW - self.col_widths[-1] )
                lidx = cs[iq-1] + termW - cs[iq] - 5
                uidx = table_width - self.col_widths[-1]
                trunc = lambda row : row[:lidx] + '<...>' + row[uidx:]
            #FIXME!

        #top line
        top_line = self.col_fmt.format( '', use_width, '^' )
        top_line = as_superstrings(top_line, 'underline')
        table.append(top_line)
        
        #make title line
        if not self.title is None:
            title_line = self.col_fmt.format( self.title, use_width, '^' )  #center align title.  THIS COULD ALSO BE AN OPTION
            title_line = self.apply_props( title_line, self.title_props ) 
            title_line = title_line.set_property('underline')
            table.append(title_line)
        
        #make rows
        for i, col_items in enumerate( self.pre_table ):
            row = self.create_row( col_items )
            if i in self.where_row_borders:
                row = as_superstrings(row, 'underline', 
                                      precision=self.num_prec )         #FIXME!!!!!!!!!!!!!
            
            row = trunc(row)
            table.append( row )
            
        self.table = table
        
        return table
    
    #====================================================================================================
    #def truncate(self, table ):
        #w,h = getTerminalSize()
        #if len(table[0]) > w:   #all rows have equal length... #np.any( np.array(list(map(len, table))) > w ):
            