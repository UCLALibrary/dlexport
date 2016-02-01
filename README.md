Use this utility to export project metadata from DLCS in CSV format.

# Setup

## Secrets

This utility requires a secret file to work.  
Email mmatney@library.ucla.edu to request the file, and move it to the root directory of this project.

## Local Deployment

### System

Python 3.4, pip3, virtualenv, and an Oracle database client must be installed on the host machine.

For the Oracle DB client, I used 'oracle-instantclient'. First, go to
http://www.oracle.com/technetwork/database/features/instant-client/index-097480.html
to choose your system platform, accept the user agreement, and download and install both "Instant Client Package - Basic" and "Instant Client Package - SDK". Installation instructions can be found on that same webpage.

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

## Remote Deployment - AWS Elastic Beanstalk

To deploy to elastic beanstalk, first install the EB CLI on your system. Then,

	cd dlexport
	eb init --region us-west-1
	eb create
	
The deployment will fail because the Oracle DB client is not installed on the server. To do this, download the Oracle DB client .rpm for both "Instant Client Package - Basic" and "Instant Client Package - SDK" (assuming we are running Amazon Linux on our EB). First, obtain a .pem with your private key in order to connect to the server. Then, transfer the files with scp, ssh to install them, and re-deploy:

	scp -v -i private-key.pem \
		oracle-instantclient12.1-basic-12.1.0.2.0-1.x86_64.rpm \
		oracle-instantclient12.1-devel-12.1.0.2.0-1.x86_64.rpm \
		ec2-user@YOUR.EC2.IP.ADDR:~/
	eb ssh
	sudo rpm -ivh \
		oracle-instantclient12.1-basic-12.1.0.2.0-1.x86_64.rpm \
		oracle-instantclient12.1-devel-12.1.0.2.0-1.x86_64.rpm
	export LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib:$LD_LIBRARY_PATH
	export PATH=/usr/lib/oracle/12.1/client64/bin:$PATH
	logout
	eb deploy

# Usage

This utility can be used at the command line. Show usage with:

	python3 dlexport.py -h

Or, run it on your localhost to use in a browser:

	python3 application.py

## Examples

Export metadata in collection 'bbb' from the 'aaa' database, and write to 'ccc.csv'.

	python3 dlexport.py -d aaa -c bbb > ccc.csv

