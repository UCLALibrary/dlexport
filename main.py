from flask import Flask, make_response, render_template, request

import dlexport


app = Flask(__name__)
exporter = dlexport.Dlexport('db-secrets.json')


def renderTemplate(errorCode=None):

    if errorCode is dlexport.ERR_INVALID_DATABASE:
        m = 'Please supply a valid database name!'
    elif errorCode is dlexport.ERR_INVALID_COLLECTION:
        m = 'Please supply a valid collection name!'
    elif errorCode is dlexport.ERR_EMPTY_COLLECTION:
        m = 'There are no items in that collection!'
    elif errorCode is dlexport.ERR_INVALID_FILENAME:
        m = 'Please choose a valid filename!'
    elif errorCode is dlexport.ERR_UNKNOWN:
        m = 'Unknown error!'
    else:
        pass
        m = 'RaiseExceptionHere'
        # TODO: raise exception
    return render_template('error.html', message=m)


@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':

        if request.form['outfile'] is '':
            return renderTemplate(dlexport.ERR_INVALID_FILENAME)

        try:
            exporter.getMetadata(
                request.form['db'],
                request.form['appname'],
                request.form['thumbnail']
                )
            response = make_response(exporter.toCsv())
            response.headers['Content-Disposition'] = (
                'attachment; filename={}.csv'.format(request.form['outfile']))
            return response

        except dlexport.DlexportException as e:
            return renderTemplate(e.err)

    elif request.method == 'GET':
        return render_template(
            'index.html',
            databases=exporter.getDatabases(True))

    else:
        return render_template(
            'error.html',
            message='Error: "{}" requests not supported, use "GET" or "POST"'.format(
                request.method))

@app.route('/edited/', methods=['GET', 'POST'])
def edited():
    if request.method == 'POST':

        if request.form['outfile'] is '':
            return renderTemplate(dlexport.ERR_INVALID_FILENAME)

        try:
            exporter.getEditedItems(
                request.form['db'],
                request.form['start_date'],
                request.form['end_date']
                )
            response = make_response(exporter.toEditedCsv())
            response.headers['Content-Disposition'] = (
                'attachment; filename={}.csv'.format(request.form['outfile']))
            return response

        except dlexport.DlexportException as e:
            return renderTemplate(e.err)

    elif request.method == 'GET':
        return render_template(
            'edited.html',
            databases=exporter.getDatabases(True))

    else:
        return render_template(
            'error.html',
            message='Error: "{}" requests not supported, use "GET" or "POST"'.format(
                request.method))


if __name__ == '__main__':
    app.run()
