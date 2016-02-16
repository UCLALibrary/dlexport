from dlexport import *
import cx_Oracle
import requests
import smtplib
from email.mime.text import MIMEText

CONN_OK = 0
CONN_ERR = 1

def pingRemoteServer(url):

    response = requests.get(url)
    status = response.status_code

    if status not in [200, 304]:
        return (CONN_ERR, status)

    return (CONN_OK, status)

def pingDatabases():

    statuses = {}
    exporter = Dlexport('db-secrets.json')

    dbs = exporter.getDatabases()

    # try to connect to each db
    for db in dbs:
        try:
            conn = exporter.connectToDb(db)
            conn.close()
            statuses[db] = CONN_OK

        except cx_Oracle.DatabaseError as e:
            # TODO: check error and print specific diagnostic message
            statuses[db] = CONN_ERR

    return statuses

def sendEmail(url, srs, dbcs):

    body = 'The application at {} is experiencing issues.\n'.format(url)
    if srs[0] == CONN_ERR:
        body += 'The server responded to a GET request with status code {}.\n'.format(srs[1])

    for k, v in dbcs:
        if v == CONN_ERR:
            body += 'The application could not connect to the database "{}".\n'.format(k)

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

    if serverResponseStatus[0] == CONN_ERR or CONN_ERR in dbConnectionStatuses.values():
        sendEmail(appUrl, serverResponseStatus, dbConnectionStatuses)
