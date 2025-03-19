import csv
import logging
import re

########################################################################################################################
# Helper class for reading and modifying *.x10 files.
########################################################################################################################

def read_x10_file(filename, null_value='NULL', encoding='utf-8'):
    x10_file = X10File()
    x10_file.null_value = null_value
    x10_file.encoding = encoding
    x10_file.read(filename)
    
    return x10_file
    
    
def create_x10_file(filename):
    x10_file = X10File(filename)
    
    return x10_file

class X10File:

    def __init__(self, filename=None):
        self.null_value = ''
        self.encoding = 'utf-8'
        self.strict = False
        
        self._internal_init()

    def read(self, filename):
        self._filename = filename
    
        with open(self._filename, newline='', encoding=self.encoding) as x10_file:
            x10_reader = csv.reader(x10_file, delimiter=';', quotechar='"')
            for x10_row in x10_reader:
                if len(x10_row) > 0:
                
                    if x10_row[0] == 'mod':
                        self.date_format = x10_row[1].strip().strip('"')
                        self.time_format = x10_row[2].strip().strip('"')
                        self.representation = x10_row[3].strip().strip('"')
                    
                    elif x10_row[0] == 'src':
                        self.creator_name = x10_row[1].strip().strip('"')
                        self.creation_date = x10_row[2].strip().strip('"')
                        self.creation_time = x10_row[3].strip().strip('"')
                        
                    elif x10_row[0] == 'chs':
                        self.charset = x10_row[1].strip().strip('"')
                        
                    elif x10_row[0] == 'ver':
                        self.file_version = x10_row[1].strip().strip('"')
                    
                    elif x10_row[0] == 'ifv':
                        self.interface_version = x10_row[1].strip().strip('"')
                        
                    elif x10_row[0] == 'dve':
                        self.data_version = x10_row[1].strip().strip('"')
                        
                    elif x10_row[0] == 'fft':
                        self.file_format = x10_row[1].strip().strip('"')
                        
                    elif x10_row[0] == 'tbl':
                        self.table_name = x10_row[1].strip().strip('"')
                        
                    elif x10_row[0] == 'atr':
                        self.attributes = list()
                        for val in x10_row[1:]:
                            self.attributes.append(val.strip().strip('"'))
                            
                    elif x10_row[0] == 'frm':
                        self.datatypes = list()
                        for val in x10_row[1:]:
                            dtype_value = re.split(r"[\[\]]", val.strip().strip('"'))
                            
                            if len(dtype_value) > 1:
                                dtype = dtype_value[0]
                                dsize = dtype_value[1]
                                
                                self.datatypes.append({'type': dtype, 'size': dsize})
                            else:
                                self.datatypes.append({'type': dtype_value[0], 'size': None})
                            
                    elif x10_row[0] == 'rec':
                        record = dict()
                        for i, val in enumerate(x10_row[1:]):
                            val = val.strip().strip('"')
                            
                            if val == '""':
                                val = ''
                                
                            dtype = self._dtype_of_fstr(self.datatypes[i]['type'], self.datatypes[i]['size'])
                            if dtype == str:
                                record[self.attributes[i]] = str(val)
                            elif dtype == int and val != self.null_value:
                                record[self.attributes[i]] = int(val)
                            elif dtype == float and val != self.null_value:
                                record[self.attributes[i]] = float(val)
                            else: # boolean is also handled as string here, since it can contain 0/1 or False/True
                                record[self.attributes[i]] = val
                               
                        self.records.append(record)
                        
                    elif x10_row[0] == 'end':
                        if not len(self.records) == int(x10_row[1]):
                            logging.error("number of records not matching")
                            
                    elif x10_row[0] == 'eof':
                        pass
                        
    def write(self, filename=None):
        if filename == None:
            filename = self._filename
    
        with open(filename, 'w', newline='', encoding=self.encoding) as x10_file:
            x10_writer = csv.writer(x10_file, delimiter=';', quotechar='*')
            
            x10_writer.writerow([
                'mod', 
                self._create_value(self.date_format, None), 
                self._create_value(self.time_format, None), 
                self._create_value(self.representation, None)
            ])
                  
            x10_writer.writerow([
                'src', 
                self._create_value(self.creator_name), 
                self._create_value(self.creation_date), 
                self._create_value(self.creation_time)
            ])
            
            x10_writer.writerow(['chs', self._create_value(self.charset)])
            x10_writer.writerow(['ver', self._create_value(self.file_version)])
            x10_writer.writerow(['ifv', self._create_value(self.interface_version)])
            x10_writer.writerow(['dve', self._create_value(self.data_version)])
            x10_writer.writerow(['fft', self._create_value(self.file_format)])
            
            # write table header
            x10_writer.writerow([])
            x10_writer.writerow(['tbl', self._create_value(self.table_name, None)])
            
            # write attributes
            f_attributes = ['atr']
            for attr in self.attributes:
                f_attributes.append(self._create_value(attr, None))
                
            x10_writer.writerow(f_attributes)
            
            # write datatypes
            f_dtypes = ['frm']
            for datatype in self.datatypes:
                dtype = datatype['type']
                dsize = datatype['size']
                
                if dsize is not None:
                    dtype_value = f"{dtype}[{dsize}]"
                    f_dtypes.append(self._create_value(dtype_value, None))
                else:
                    dtype_value = f"{dtype}"
                    f_dtypes.append(self._create_value(dtype_value, None))
                
            x10_writer.writerow(f_dtypes)
            
            # write records
            f_records = list()
            for record in self.records:
                
                f_record = ['rec']
                for rkey in record:
                    
                    column_index = self.attributes.index(rkey)
                    
                    fstr = self.datatypes[column_index]['type']
                    fsize = self.datatypes[column_index]['size']
                    dtype = self._dtype_of_fstr(fstr, fsize)
                    
                    f_record.insert(column_index + 1, self._create_value(record[rkey], dtype))
                    
                f_records.append(f_record)
                
            x10_writer.writerows(f_records)
            
            # write table end
            x10_writer.writerow(['end', self._create_value(len(self.records), int)])
            
            # write file end
            x10_writer.writerow(['eof', self._create_value(1, int)])
            
    def add_column(self, cname, dtype, dsize, default=''):
        self.attributes.append(cname)
        
        fstr = self._fstr_of_dtype(dtype)
        fsize = str(dsize) if dtype == str else f"{dsize}.0"
        
        self.datatypes.append({'type': self._fstr_of_dtype(dtype), 'size': fsize})
        
        for record in self.records:
            record[cname] = default
            
    def remove_column(self, cname):
        column_index = self.attributes.index(cname)
        
        del self.attributes[column_index]
        del self.datatypes[column_index]
        
        for record in self.records:
            del record[cname]
            
    def add_record(self, rdata, primary_key=None):
        record_existing = False
        record_pkfields = self._create_compare_record(rdata, primary_key)
        for i in range(len(self.records)):
            compare_record = self._create_compare_record(self.records[i], primary_key)
            
            if record_pkfields == compare_record:
                record_existing = True
                break
                
        if not record_existing:
            self.records.append(rdata)
            
    def remove_records(self, rdata, primary_key=None):
        updated_records = list()
        for i in range(len(self.records)):
            compare_record = self._create_compare_record(self.records[i], primary_key)
            
            if rdata != compare_record:
                updated_records.append(self.records[i])
                
        self.records = updated_records 

    def find_records(self, rdata, primary_key=None):
        rdata = self._create_compare_record(rdata, primary_key)
        
        result_records = list()
        for i in range(len(self.records)):
            compare_record = self._create_compare_record(self.records[i], primary_key)

            if rdata == compare_record:
                result_records.append(self.records[i])

        return result_records
    
    def find_record(self, rdata, primary_key=None):
        rdata = self._create_compare_record(rdata, primary_key)
        
        for i in range(len(self.records)):
            compare_record = self._create_compare_record(self.records[i], primary_key)

            if rdata == compare_record:
                return self.records[i]
            
    def replace_foreign_keys(self, foreign_key_columns, repl_map):
        for i in range(len(self.records)):
            original_record = self.records[i]
            updated_record = dict(original_record)
            
            updated = False
            for fkc in foreign_key_columns:
                if original_record[fkc] in repl_map:
                    updated_record[fkc] = repl_map[original_record[fkc]]
                    updated = True
                    
            if updated:
                self.records[i] = updated_record
            
    def close(self):
        self._internal_init()
        
    def _internal_init(self):
        
        self._filename = None
        
        self.date_format = None
        self.time_format = None
        self.representation = None
        self.creator_name = None
        self.creation_date = None
        self.creation_time = None
        self.charset = None
        self.file_version = None
        self.interface_version = None
        self.data_version = None
        self.file_format = None
        self.table_name = None
        self.attributes = list()
        self.datatypes = list()
        self.records = list()
                          
            
    def _create_value(self, val, dtype=str):
        
        if dtype == str:
            return f" \"{val}\""
        else:
            return f" {val}"
            
    def _dtype_of_fstr(self, fstr, fsize=None):
        
        if fstr == 'char':
            return str
        elif fstr == 'boolean':
            return bool
        elif fstr == 'num' and fsize is not None:
            decimal_places = int(fsize.split('.')[1])
            if decimal_places > 0:
                return float
            else:
                return int
        else:
            return int
            
    def _fstr_of_dtype(self, dtype):
        
        if dtype == str:
            return 'char'
        elif dtype == bool:
            return 'boolean'
        else:
            return 'num'
        
    def _create_compare_record(self, record, primary_key):
    
        if primary_key is not None:
            compare_record = dict(record)
            if primary_key is not None:
                for k in record:
                    if k not in primary_key:
                        del compare_record[k]
                        
            return compare_record
        else:
            return record
