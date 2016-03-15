from dlexport import *
import cx_Oracle
import requests
import smtplib
from email.mime.text import MIMEText

NAGIOS_OK = 0
NAGIOS_WARNING = 1
NAGIOS_CRITICAL = 2
NAGIOS_UNKNOWN = 3

SERVER_CONN_OK = 0
SERVER_CONN_ERR = 1

DB_CONN_OK = 2
DB_CONN_ERR = 3


def pingRemoteServer(url):

    """
    Send GET request to the url and return a 2-tuple, with the first element
    indicating whether the request returned a success response or not, and the 
    second containing the actual response status.
    """
    response = requests.get(url)
    status = response.status_code

    if status not in [200, 304]:
        return (SERVER_CONN_ERR, status)

    return (SERVER_CONN_OK, status)

def pingDatabases():

    statuses = {}
    exporter = Dlexport('db-secrets.json')

    dbs = exporter.getDatabases()

    # try to connect to each db
    for db in dbs:
        try:
            conn = exporter.connectToDb(db)
            conn.close()
            statuses[db] = DB_CONN_OK

        except cx_Oracle.DatabaseError as e:
            # TODO: check error and print specific diagnostic message
            statuses[db] = DB_CONN_ERR

    return statuses

def sendEmail(url, srs, dbcs):

    body = 'The application at {} is experiencing issues.\n'.format(url)
    if srs[0] == SERVER_CONN_ERR:
        body += 'The server responded to a GET request with status code {}.\n'.format(srs[1])

    for k, v in dbcs:
        if v == DB_CONN_ERR:
            body += 'The application could not connect to the database "{}".\n'.format(k)

    print(body)

    sender = 'mmatney@library.ucla.edu'
    receivers = ['mmatney@library.ucla.edu']

    msg = MIMEText(body)
    msg['Subject'] = 'Monitoring {}'.format(url)
    msg['From'] = 'donotreply'
    msg['To'] = 'markamatney@gmail.com'
    #msg['To'] = 'mmatney@library.ucla.edu'

    s = smtplib.SMTP(host='localhost', port=8025)
    s.send_message(msg)
    s.quit()


if __name__ == '__main__':

    appUrl = 'http://dlexport-dev.us-west-1.elasticbeanstalk.com/'
    serverResponseStatus = pingRemoteServer(appUrl)
    dbConnectionStatuses = pingDatabases()
    nagiosRetval = NAGIOS_OK

    if serverResponseStatus[0] == SERVER_CONN_ERR or DB_CONN_ERR in dbConnectionStatuses.values():

    	body = 'The application at {} is experiencing issues.\n'.format(url)
        if serverResponseStatus[0] == SERVER_CONN_ERR:
            body += 'CRITICAL: The server responded to a GET request with status code {}.\n'.format(serverResponseStatus[1])
	    nagiosRetval = NAGIOS_CRITICAL
    
        for k, v in dbcs:
            if v == DB_CONN_ERR: # and k is not production DB - else CRITICAL
                body += 'WARNING: The application could not connect to the database "{}".\n'.format(k)
		if (nagiosRetval < NAGIOS_WARNING):
		    nagiosRetval = NAGIOS_WARNING

    else:
        body = 'All ok.'

    print(body)
    exit(nagiosRetval)
