'''
dlexport.py

Export project metadata from DLCS to CSV or JSON format.
'''

import argparse
import csv
import cx_Oracle
import functools
import io
from json import loads, dumps
import os
import pprint
import re

os.environ['NLS_LANG'] = '.UTF8'


SUCCESS = 0
ERR_INVALID_DATABASE = 1
ERR_INVALID_COLLECTION = 2
ERR_EMPTY_COLLECTION = 3
ERR_INVALID_FILENAME = 4
ERR_UNKNOWN = 5
ERR_INVALID_QUERY = 6
# TODO: change codes to strings


def clean(dirty):
    '''
    Returns a cleaned string, stripped of all newlines and carriage returns.
    '''
    return dirty.replace('\r', '').replace('\n', '')


class DlexportException(Exception):
    '''
    Throw if anything in the Dlexport class goes wrong.
    '''

    def __init__(self, errorCode):
        self.err = errorCode

    def __str__(self):
        return repr(self.err)


class Dlexport:
    '''
    Exporter class.
    '''

    def __init__(self, secretsFile):
        '''
        Stores secrets in 'private' data mamber.
        '''
        with open(secretsFile) as f:
            self._secrets = loads(f.read())

    def connectToDb(self, db):
        '''
        Opens and returns a database connection handle.
        '''
        if db not in self.getDatabases():
            raise DlexportException(ERR_INVALID_DATABASE)

        database = self._secrets[db]
        ip = database['ip']
        port = database['port']
        sid = database['sid']

        # assume the following will succeed if the secrets file is not modified
        dnsTns = cx_Oracle.makedsn(ip, port, sid)
        return cx_Oracle.connect(
            database['username'],
            database['password'],
            dnsTns)

    def getDbQuery(self, db, query):
        '''
        Returns the desired query to be run on the given db.
        '''
        dbs = self._secrets
        if db not in list(dbs.keys()):
            raise DlexportException(ERR_INVALID_DATABASE)

        queries = dbs[db]['queries']
        if query not in list(queries):
            raise DlexportException(ERR_INVALID_QUERY)

        return queries[query]

    def getDbCollections(self, db):
        '''
        Returns a list of the given db's collections.
        The inner list always has two elements, project_title and webapp_name.
        '''
        conn = self.connectToDb(db)
        cursor = conn.cursor()

        query = self.getDbQuery(db, 'collections')
        cursor.execute(query)
        dbCollections = [[a, b] for a, b in cursor]

        cursor.close()
        conn.close()

        return dbCollections

    def getDatabases(self, includeCollections=False):
        '''
        Returns a list of databases.
        The returned list may include a list of the collections for each db.
        '''
        # Get list of keys in the secrets
        db_list = [a for a in self._secrets]
        if includeCollections is True:
            # this will not throw an exception
            return [[a, self.getDbCollections(a)] for a in db_list]
        else:
            return db_list

    def isDb(self, db):
        '''
        Checks if db exists.
        '''
        if db in self.getDatabases():
            return True
        else:
            return False

    def isCollectionInDb(self, collection, db):
        '''
        Check if collection_name is valid (exists in the given db).
        '''
        collections = [item[1] for item in self.getDbCollections(db)]
        if collection in collections:
            return True
        else:
            return False

    def getMetadata(self, db=None, collection=None, thumbnails=False, masters=False):
        '''
        Get the metadata and store in data member,
        '''
        # check for valid database name
        if db not in self.getDatabases():
            print('Error: invalid database name!')
            raise DlexportException(ERR_INVALID_DATABASE)

        # check for valid collection to prevent SQL injection
        if not self.isCollectionInDb(collection, db):
            print('Error: invalid collection name!')
            raise DlexportException(ERR_INVALID_COLLECTION)

        # connect to Oracle DB and execute query
        conn = self.connectToDb(db)
        cursor = conn.cursor()

        query = self.getDbQuery(db, 'metadata').format(collection)
        cursor.execute(query)

        # go thru query results, organize metadata in dictionary keyed by item_ark
        # keep track of all 2nd-tier keys
        # count number of rows in result
        metadata = {}
        csvHeaders = ['Project Name', 'Item Title', 'Item Ark', 'Item Sequence']
        nRows = 0

        for (project_title, node_title, item_ark, item_sequence,
             desc_term_label, qualifier_label, text_value) in cursor:

            nRows += 1

            # check if we've started accounting for this item yet
            if item_ark not in metadata:
                metadata[item_ark] = {
                    'Project Name': project_title,
                    'Item Title': node_title,
                    'Item Ark': item_ark,
                    'Item Sequence': '' if item_sequence is None else str(item_sequence)
                }
            if qualifier_label is None:
                inner_dict_key = desc_term_label
            else:
                inner_dict_key = '{0}.{1}'.format(desc_term_label, qualifier_label)

            # check if we've encountered a new header field
            if inner_dict_key not in csvHeaders:
                csvHeaders.append(inner_dict_key)

            # check if inner_dict_key already maps to a value
            if inner_dict_key in metadata[item_ark]:
                metadata[item_ark][inner_dict_key] = '{0}|~|{1}'.format(
                    metadata[item_ark][inner_dict_key],
                    text_value
                )
            else:
                metadata[item_ark][inner_dict_key] = text_value

        cursor.close()

        # check if we want thumbnails too
        if thumbnails:
            csvHeaders.append('thumbnailImageName')
            cursor = conn.cursor()
            query = self.getDbQuery(db, 'thumbnailImageName').format(collection)
            cursor.execute(query)

            for (item_ark, file_name) in cursor:
                metadata[item_ark]['thumbnailImageName'] = file_name

            cursor.close()

        # check if we want masters too
        if masters:
            csvHeaders.append('masterImageName')
            cursor = conn.cursor()
            query = self.getDbQuery(db, 'masterImageName').format(collection)
            cursor.execute(query)

            for (item_ark, file_name) in cursor:
                metadata[item_ark]['masterImageName'] = file_name

            cursor.close()

        conn.close()

        if nRows == 0:
            print('Error: collection "{}" has no items!'.format(collection))
            raise DlexportException(ERR_EMPTY_COLLECTION)

        self.csvHeaders = csvHeaders
        self.metadata = metadata

    def toJson(self):
        '''
        Returns JSON representation of the metadata.
        '''
        # print JSON representation to stdout
        # TODO: check that self.metadata exists
        return dumps(self.metadata,sort_keys=True,indent=4,separators=(',',': '))

    def toCsv(self):
        '''
        Returns CSV representation of the metadata.
        '''
        f = io.StringIO()
        csvWriter = csv.writer(
            f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

        # write header
        csvWriter.writerow([clean(i) for i in self.csvHeaders])

        # write a line for each item in the collection
        for k, v in sorted(self.metadata.items(), key=lambda x: x[0]):
            try:
                cleanedValuesList = [
                    clean(v[i])
                    # check csvHeaders to determine if value should be
                    # included
                    if i in v and v[i] is not None else ''
                    for i in self.csvHeaders
                ]
            except AttributeError as e:
                print(i, v[i])
                raise
            csvWriter.writerow(cleanedValuesList)
        return f.getvalue()


if __name__ == '__main__':
    '''
    Main routine.
    '''
    try:
        # parse command line arguments
        parser = argparse.ArgumentParser(
            description='Export project metadata from DLCS.')
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
            '-q', '--quiet',
            default=False,
            action='store_true',
            required=False,
            help='suppress all standard output, except for error mesages')
        parser.add_argument(
            '-t', '--thumbnails',
            default=False,
            action='store_true',
            required=False,
            help='include thumbnail file names in the output')
        parser.add_argument(
            '-m', '--masters',
            default=False,
            action='store_true',
            required=False,
            help='include master file names in the output')

        # TODO: add args to choose btw json, csv, and xml
        # TODO: arg to choose char encoding (UTF-8, UTF-16, etc.)

        argsNamespace = parser.parse_args()

        exporter = Dlexport('db-secrets.json')
        exporter.getMetadata(argsNamespace.database, argsNamespace.collection, argsNamespace.thumbnails, argsNamespace.masters)

        if not argsNamespace.quiet:
            # TODO: add switch on output formats (json, xml, etc.)
            print(exporter.toCsv())
        exit(SUCCESS)

    except DlexportException as e:
        exit(e.err)
