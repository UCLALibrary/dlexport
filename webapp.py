import dlexport
from flask import Flask, make_response, render_template, request
import subprocess

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':

        outfile = request.form['outfile']
        exit_status = subprocess.call(['python3', 'dlexport.py', '--database', request.form['db'], '--collection', request.form['appname'], '--write', '{}.csv'.format(outfile)])

        if exit_status == dlexport.SUCCESS:
            with open('csv/{}.csv'.format(outfile), 'r') as f:
                body = f.read()
            response = make_response(body)
            response.headers['Content-Disposition'] = (
                'attachment; filename={}.csv'.format(outfile))
            return response
            # TODO: delete files on server after download

        elif exit_status == dlexport.ERR_INVALID_DATABASE:
            return render_template('error.html',
                message='Please supply a valid database name!')

        elif exit_status == dlexport.ERR_INVALID_COLLECTION:
            return render_template('error.html',
                message='Please supply a valid collection name!')

        elif exit_status == dlexport.ERR_INVALID_FILENAME:
            return render_template('error.html',
                message='Please supply a valid file name!')

        elif exit_status == dlexport.ERR_EMPTY_COLLECTION:
            return render_template('error.html',
                message='There are no items in that collection!')

        else:
            return render_template('error.html',
                message='Unknown error!')

    elif request.method == 'GET':
        # populate dropdown menu with all collection names
        #return render_template('index.html', databases=dlexport.get_databases(), json_databases=dlexport.dumps(dlexport.get_databases()), collections=dlexport.get_databases(True))
        return render_template('index.html', databases=dlexport.get_databases(True))
        # TODO: add dropdown option for char encoding of csv output

    else:
        return render_template('error.html',
            message='Error: "{}" requests not supported, use "GET" or "POST"'.format(request.method))

if __name__ == '__main__':
    app.run()
