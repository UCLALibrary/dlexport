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

METADATA_QUERY = """
SELECT 
    c.project_title, 
    b.item_ark, 
    b.item_sequence,
    b.statusid_fk,
    q.status,
    a.desc_term_label, 
    a.core_desc_term, 
    a.qualifier_label, 
    a.text_value, 
    parent_join.item_ark AS parent_ark, 
    v_ot.object_type, 
    CASE
        WHEN p_ot.object_type IS NOT NULL
        THEN p_ot.object_type
        ELSE ''
    END AS parent_obj_type, 
    cf.file_name, cf.file_location
--a.desc_term_label, a.qualifier_label, parent_join.item_ark as parent_ark, b.item_ark, v_ot.object_type, a.text_value as tv 
FROM 
    (SELECT 
        dv.divid_fk AS item_id, 
        dv.projectid_fk AS project_id, 
        cdt.desc_term AS core_desc_term, 
        cdt.core_desc_termid_pk AS core_desc_termid_id, 
        dt.term_label AS desc_term_label, 
        dt.desc_termid_pk AS desc_termid_id, 
        v_qual.qual_text AS qualifier_label,
        CASE 
            WHEN dv.desc_cvid_fk IS NOT NULL 
            THEN ctrl_values.ctrl_val_text 
            ELSE dv.desc_value 
        END AS text_value, 
        dv.desc_cvid_fk AS desc_control_values_id, 
        dv.desc_qualifierid_fk AS desc_qualifiers_id, 
        v_qual.qid AS core_desc_qualifiers_id, 
        ctrl_values.core_desc_cvid_pk AS core_desc_control_values_id 
    FROM desc_values dv, desc_terms dt, core_desc_terms cdt, 
        (SELECT DISTINCT 
            dq.core_desc_qualifierid_fk AS qid, 
            cdq.desc_qualifier AS qual_text, 
            dq.desc_qualifierid_pk AS desc_qual_pk 
        FROM desc_qualifiers dq, core_desc_qualifiers cdq 
        WHERE dq.CORE_DESC_QUALIFIERID_FK = cdq.core_desc_qualifierid_pk ) v_qual,
        (SELECT DISTINCT 
            cdcv.core_desc_cv AS ctrl_val_text, 
            dcv.desc_cvid_pk, 
            cdcv.core_desc_cvid_pk 
        FROM core_desc_control_values cdcv, desc_control_values dcv 
        WHERE cdcv.core_desc_cvid_pk = dcv.core_desc_cvid_fk ) ctrl_values 
    WHERE dv.desc_termid_fk = dt.desc_termid_pk 
    AND dt.core_desc_termid_fk = cdt.CORE_DESC_TERMID_PK 
    AND dv.desc_qualifierid_fk = v_qual.desc_qual_pk(+) 
    AND dv.desc_cvid_fk = ctrl_values.desc_cvid_pk(+)
    ) a 

INNER JOIN project_items b 
ON a.item_id = b.divid_pk 

INNER JOIN projects c 
ON b.projectid_fk = c.projectid_pk 

LEFT OUTER JOIN qa_status q
ON b.statusid_fk = q.statusid_pk

INNER JOIN 
    (SELECT objectid_pk, object_label, object_type
    FROM dl_objects, dl_object_types
    WHERE object_typeid_fk = object_typeid_pk
    ) v_ot
ON v_ot.objectid_pk = b.objectid_fk 

LEFT OUTER JOIN content_files cf
ON b.divid_pk = cf.divid_fk 
AND cf.file_use = 'Master'

LEFT OUTER JOIN project_items parent_join
ON b.parent_divid = parent_join.divid_pk

LEFT OUTER JOIN 
    (SELECT objectid_pk, object_label, object_type
    FROM dl_objects, dl_object_types
    WHERE object_typeid_fk = object_typeid_pk
    ) p_ot
ON p_ot.objectid_pk = parent_join.objectid_fk

WHERE project_id IN 
    (SELECT projectid_pk 
    FROM projects 
    WHERE webapp_name = :collection )
"""


COLLECTIONS_QUERY = """
SELECT project_title, webapp_name 
FROM projects 
ORDER BY project_title
"""


THUMBNAIL_QUERY = """
SELECT pi.item_ark, cf.file_name, cf.file_location 
FROM projects p 
    INNER JOIN project_items pi ON p.projectid_pk = pi.projectid_fk 
    INNER JOIN content_files cf ON pi.divid_pk = cf.divid_fk 
WHERE cf.file_use = 'Thumbnail' 
AND p.webapp_name = :collection 
ORDER BY pi.item_ark
"""
   

MASTER_IMG_QUERY = """
SELECT pi.item_ark, cf.file_name, cf.file_location 
FROM projects p 
INNER JOIN project_items pi ON p.projectid_pk = pi.projectid_fk 
INNER JOIN content_files cf ON pi.divid_pk = cf.divid_fk 
WHERE cf.file_use = 'Master' 
AND p.webapp_name = :collection 
ORDER BY pi.item_ark
"""

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

    def getDbCollections(self, db):
        '''
        Returns a list of the given db's collections.
        The inner list always has two elements, project_title and webapp_name.
        '''
        conn = self.connectToDb(db)
        cursor = conn.cursor()
        cursor.execute(COLLECTIONS_QUERY)
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
        cursor.prepare(METADATA_QUERY)
        cursor.execute(None, collection=collection)

        # go thru query results, organize metadata in dictionary keyed by item_ark
        # keep track of all 2nd-tier keys
        # count number of rows in result
        metadata = {}
        csvHeaders = ['Project Name','Item ARK', 'QA Status ID', 'QA Status', 'Parent ARK', 'Object Type', 'File Name', 'Item Sequence', 'Duplicate']
        nRows = 0

        for (project_title, item_ark, item_sequence, statusid_fk, status, desc_term_label, 
            core_desc_term, qualifier_label, text_value, parent_ark, 
            object_type, parent_obj_type, file_name, file_location) in cursor:

            nRows += 1

            if object_type != 'Collection':
                if parent_obj_type == 'Collection':
                    object_type = 'Work'
                else:
                    object_type = 'ChildWork'

            # check if we've started accounting for this item yet
            if item_ark not in metadata:
                file_location_str = ''
                if file_location:
                    indexOfdigi = len("http://digilib.library.ucla.edu/")
                    file_location_str = file_location[indexOfdigi:]

                #add ark:/ format to ark string for csv output
                readable_item_ark = 'ark:/' + str(item_ark)
                #check if this item has a parent ark because the collection level item will not
                if parent_ark == None:
                    readable_parent_ark = ''
                else:
                    readable_parent_ark = 'ark:/' + str(parent_ark)

                #change statusid_fk to a string
                qa_status = str(statusid_fk)

                metadata[item_ark] = {
                    'Project Name': project_title,
                    'Item ARK': readable_item_ark,
                    'QA Status ID': qa_status,
                    'QA Status': status,
                    'Parent ARK': readable_parent_ark,
                    'Object Type': object_type,
                    'File Name': file_location_str,
                    'Item Sequence': '' if item_sequence is None else str(item_sequence)
                                    
                }


            if qualifier_label in (False, None) or len(qualifier_label) <= 0:
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

            #check if the title field contains the word 'duplicate'
            if desc_term_label == "Title":
                if  metadata[item_ark][inner_dict_key] == text_value:
                    string_text_value = (str(text_value)).lower()
                    if (bool(re.search(r"\bduplicate", string_text_value)) == True) or (bool(re.search(r"\bdup ", string_text_value)) == True):
                        metadata[item_ark]['Duplicate'] = 'true'
            else:
                pass

        cursor.close()

        # check if we want thumbnails too
        if thumbnails:
            csvHeaders.append('thumbnailImageName')
            cursor = conn.cursor()
            cursor.prepare(THUMBNAIL_QUERY)
            cursor.execute(None, collection=collection)

            for (item_ark, file_name, file_location) in cursor:           
                metadata[item_ark]['thumbnailImageName'] = file_name

            cursor.close()

        # check if we want masters too
        if masters:
            csvHeaders.append('masterImageName')
            cursor = conn.cursor()
            cursor.prepare(MASTER_IMG_QUERY)
            cursor.execute(None, collection=collection)

            for (item_ark, file_name, file_location) in cursor:
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
