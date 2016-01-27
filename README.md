Use this utility to export project metadata from DLCS in CSV or JSON format.

# Setup

### System

Python 3.4, pip3, virtualenv, and an Oracle database client must be installed on the host machine.

For the Oracle db client, I used 'oracle-instantclient'. First, go to
http://www.oracle.com/technetwork/database/features/instant-client/index-097480.html
to choose your system platform, accept the user agreement, and download and install "Instant Client Package - SDK".

On Ubuntu, you can do the following to complete the installation:

	cd /path/to/download
	sudo alien oracle-instantclient12.1-devel-12.1.0.2.0-1.x86_64.rpm # use the name of the file you downloaded earlier
	sudo dpkg -i oracle-instantclient12.1-devel_12.1.0.2.0-2_amd64.deb

### Python Environment

Install virtualenv, then setup a virtual environment and install dependencies using the included requirements.txt:

	sudo pip3 install virtualenv
	cd dlexport
	virtualenv venv-dlexport # create virtualenv
	. venv-dlexport/bin/activate # start up virtualenv
	pip3 install -r requirements.txt

To exit your virtual environment:

	deactivate
	
To destroy it:

	rm -rf venv-dlexport

### Secrets

This utility requires a secret file to work.  
Email mmatney@library.ucla.edu to request the file, and move it to the root directory of this project.

# Usage

This utility can be used at the command line. Show usage with:

	python3 dlexport.py -h

Or, run it on your localhost to use in a browser:

	python3 webapp.py

### Examples

Export metadata in collection 'aaa' from the 'bbb' database, and write to 'ccc.csv'.

	python3 dlexport.py -d aaa -c bbb -w ccc.csv

Export metadata in collection 'aaa' from the 'bbb' database, and write to stdout in JSON format.

	python3 dlexport.py -d aaa -c bbb

Export metadata in collection 'aaa' from the 'bbb' database, and write to 'ccc.json'.

	python3 dlexport.py -d aaa -c bbb > ccc.json

