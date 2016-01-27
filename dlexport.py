'''
dlexport.py

Export project metadata from DLCS to CSV or JSON format.
'''

import argparse
import csv
import cx_Oracle
import functools
from json import loads, dumps
import os
import pprint
import re

os.environ['NLS_LANG'] = '.UTF8'

# Exit codes

SUCCESS = 0
ERR_INVALID_DATABASE = 1
ERR_INVALID_COLLECTION = 2
ERR_INVALID_FILENAME = 3
ERR_EMPTY_COLLECTION = 4

# Exception to throw if anything her goes wrong

class DlexportException(Exception):
    def __init__(self, error_code):
        self.err = error_code
    def __str__(self):
        return repr(self.err)

# Functions

def clean(dirty):
    '''
    Returns a cleaned string, stripped of all newlines and carriage returns.
    '''
    return dirty.replace('\r', '').replace('\n', '')
    
def connect_to_db(name):
    '''
    Opens and returns a database connection handle.
    '''
    # TODO: may need to change path to db-secrets.json, depending on where it will live on the server
    database = loads(open('db-secrets.json').read())[name]
    ip = database['ip']
    port = database['port']
    SID = database['SID']
    dsn_tns = cx_Oracle.makedsn(ip, port, SID)
    return cx_Oracle.connect(database['username'], database['password'], dsn_tns)

def get_db_query(database, query):
    '''
    Returns the desired query to be run on the given db.
    '''
    # TODO: may need to change path to db-secrets.json, depending on where it will live on the server
    return loads(open('db-secrets.json').read())[database]['queries'][query]

def get_collections(database):
    '''
    Returns a list of the given database's collections.
    The inner list always has two elements, project_ttle and webapp_name.
    '''
    conn = connect_to_db(database)
    cursor = conn.cursor()
    get_collections_query = get_db_query(database, 'collections')
    cursor.execute(get_collections_query)
    return [[a, b] for a, b in cursor]

def get_databases(include_collections=False):
    '''
    Returns a list of databases.
    The returned list may include a list of the collections for each database.
    '''
    # TODO: may need to change path to db-secrets.json, depending on where it will live on the server
    db_list = [a for a in loads(open('db-secrets.json').read())]
    if include_collections:
        return [[a, get_collections(a)] for a in db_list]
    else:
        return db_list

def is_valid_collection(collection_name, database):
    '''
    Check if collection_name is valid (exists in the given database).
    '''
    collection_names = [item[1] for item in get_collections(database)]
    if collection_name in collection_names:
        return True
    else: 
        return False

def is_valid_filename(folder, filename):
    '''
    Returns true if the filename is in the given folder, false otherwise.
    Used to check for directory traversal attack.
    '''
    # TODO: move the following two lines outside of this function, and pass abspaths to this function instead
    # in that case, make sure to change the test for file name length == 0
    folder_path = os.path.abspath(folder)
    file_path = os.path.abspath(os.path.join(folder, filename))

    if os.path.commonprefix([folder_path, file_path]) != folder_path or os.path.split(file_path)[0] != folder_path or len(os.path.splitext(filename)[1]) == 0:
        return False
    else:
        return True

# Main routine

def main():

    # parse command line arguments 
    parser = argparse.ArgumentParser(
        description='Export project metadata from DLCS in a specified format.')
    parser.add_argument(
        '-d', '--database',
        metavar='db',
        required=True,
        help='database to use')
    parser.add_argument(
        '-c', '--collection',
        metavar='appname',
        required=True,
        help='digital collection to extract metadata from')
    parser.add_argument(
        '-w', '--write',
        metavar='outfile',
        required=False,
        help='CSV output file (if omitted, write JSON to stdout)')
    parser.add_argument(
        '-q', '--quiet',
        default=False,
        action='store_true',
        required=False,
        help='suppress all standard output, except for error mesages')
    parser.add_argument(
        '-p', '--print-query',
        default=False,
        action='store_true',
        required=False,
        help='output query that is used to extract metadata, then exit immediately')

    # TODO: arg to choose char encoding (UTF-8, UTF-16, etc.)

    args_namespace = parser.parse_args()
    application_name = args_namespace.collection
    output_file = args_namespace.write
    data_base = args_namespace.database
    quiet = args_namespace.quiet
    only_print_query = args_namespace.print_query

    # check for valid database name
    data_bases = get_databases()
    if data_base not in data_bases:
        print('Error: invalid database name!')
        raise DlexportException(ERR_INVALID_DATABASE)

    # check for valid application_name to prevent SQL injection
    if not is_valid_collection(application_name, data_base):
        print('Error: invalid collection name!')
        raise DlexportException(ERR_INVALID_COLLECTION)
    
    # check for valid output file name to prevent directory traversal attack
    if output_file != None and not is_valid_filename('csv', output_file):
        print('Error: invalid output file name!')
        raise DlexportException(ERR_INVALID_FILENAME)

    # connect to Oracle DB and execute query
    conn = connect_to_db(data_base)
    cursor = conn.cursor()
    export_metadata_query = get_db_query(data_base, 'metadata').format(application_name)
    if only_print_query:
        print(export_metadata_query)
        return SUCCESS

    cursor.execute(export_metadata_query)
    
    # go thru query results, organize metadata in dictionary keyed by item_ark
    # keep track of all 2nd-tier keys
    # count number of rows in result
    metadata = {}
    CSV_headers = ['Project Name', 'Item Title', 'Item Ark']
    n_rows = 0
    
    for (project_title, node_title, item_ark, 
         desc_term_label, qualifier_label, text_value) in cursor:
    

        n_rows += 1
    
        # check if we've started accounting for this item yet
        if item_ark not in metadata:
            metadata[item_ark] = {
                'Project Name': project_title,
                'Item Title': node_title,
                'Item Ark': item_ark
                }
        if qualifier_label == None:
            inner_dict_key = desc_term_label
        else:
            inner_dict_key = '{0}.{1}'.format(desc_term_label, qualifier_label)
    
        # check if we've encountered a new header field
        if inner_dict_key not in CSV_headers:
            CSV_headers.append(inner_dict_key)
    
        # check if inner_dict_key already maps to a value
        if inner_dict_key in metadata[item_ark]:
            metadata[item_ark][inner_dict_key] = '{0}|~|{1}'.format(
                metadata[item_ark][inner_dict_key],
                text_value
                )
        else:   
            metadata[item_ark][inner_dict_key] = text_value
    
    if n_rows == 0:
        print('Error: collection "{}" has no items!'.format(application_name))
        # TODO: throw exception instead?
        raise DlexportException(ERR_EMPTY_COLLECTION)
    
    # TODO: if using the browser GUI, use a /tmp file instead
    if output_file != None:
        # transform python dictionary into CSV and write to file
        with open(os.path.join('csv', output_file), 'w', newline='', encoding='utf-8') as f:

            filewriter = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    
            # write header
            filewriter.writerow([clean(i) for i in CSV_headers])
            
            # write a line for each item in the collection
            for k, v in sorted(metadata.items(), key=lambda x: x[0]):
                try:
                    sanitized_values_list = [
                        clean(v[i])
                        # check CSV_headers to determine if value should be included
                        if i in v and v[i] != None else ''
                        for i in CSV_headers
                        ]
                except AttributeError as e:
                    print(i, v[i])
                    raise
                filewriter.writerow(sanitized_values_list)

    elif not quiet:
        # print JSON representation to stdout
        print(dumps(metadata, sort_keys=True, indent=4, separators=(',', ': ')))

    cursor.close()
    conn.close()
    return SUCCESS

if __name__ == '__main__':
    try:
        if main() is SUCCESS:
            exit(SUCCESS)
    except DlexportException as e:
        exit(e.err)
