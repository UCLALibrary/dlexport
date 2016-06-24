# Secrets

This utility requires a secret file for both local and remote hosting. Email mmatney@library.ucla.edu to request the file, and move it to the root directory of this project.

# Local Hosting

### System

Python 3.4, pip3, virtualenv, and an Oracle database client must be installed on the host machine.

For the Oracle DB client, I used 'oracle-instantclient'. First, go [here](http://www.oracle.com/technetwork/database/features/instant-client/index-097480.html)
to choose your system platform, accept the user agreement, and download and install both "Instant Client Package - Basic" and "Instant Client Package - SDK". Installation instructions can be found at the bottom of that webpage.

### Python Environment

Install virtualenv, then setup a virtual environment and install dependencies using the included requirements.txt:

```Shell
sudo pip3 install virtualenv
cd dlexport
virtualenv venv-dlexport # create virtualenv
. venv-dlexport/bin/activate # start up virtualenv
pip3 install -r requirements.txt
```

### Testing

To run the automated tests (with virtualenv up and running):

```Shell
python3 dlexport-test.py -v
```

### CLI

Keep the virtualenv running to use this utility at the command line. Show usage with:

```Shell
python3 dlexport.py -h
```

For example, to export metadata (including thumbnail image names and master image names) from the Aldous Huxley Collection in the production DLCS database to 'myFile.csv':

```Shell
python3 dlexport.py -t -m -d lit106 -c huxle > myFile.csv # yes, it is actually named 'huxle'
```
or, in long form:
```Shell
python3 dlexport.py --thumbnails --masters --database lit106 --collection huxle > myFile.csv
```

### GUI

Here's how to run the web app on localhost:

```Shell
python3 application.py
```

### Cleanup

To exit your virtual environment:

```Shell
deactivate
```

To destroy it forever:

```Shell
rm -rf venv-dlexport
```

# Remote Hosting - AWS Elastic Beanstalk

To deploy the web app to Elastic Beanstalk, first [install the EB CLI](http://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3-install.html) on your system. Then:

```Shell
cd dlexport
eb init
```

There will be a series of prompts.

For "default region", select US West (N. California).

For "aws-access-id" and "aws-secret-key", go [here](http://docs.aws.amazon.com/general/latest/gr/getting-aws-sec-creds.html) and follow the instructions for "Access keys (access key ID and secret access key)". When prompted, click "Download Key File" to get a .csv containing your credentials to enter. Now back to the command line.

For "application to use", create a new application. Choose Python 3.4, and setup SSH with a new key pair. Now create a new single-instance environment:

```Shell
eb create --single
```

The deployment will fail with

	ERROR: Your requirements.txt is invalid. Snapshot your logs for details.

because the Oracle DB client is not installed on the server. To fix this, go [here](http://www.oracle.com/technetwork/database/features/instant-client/index-097480.html) to download the Oracle DB client .rpm for both "Instant Client Package - Basic" and "Instant Client Package - SDK" (assuming we are running Amazon Linux on our EB instance). Then, transfer the files with scp, ssh to install them, and re-deploy:

```Shell
# your file paths may differ
scp \
	oracle-instantclient12.1-basic-12.1.0.2.0-1.x86_64.rpm \
	oracle-instantclient12.1-devel-12.1.0.2.0-1.x86_64.rpm \
	ec2-user@YOUR.EC2.DOMAIN.NAME:~
eb ssh
sudo rpm -i \
	oracle-instantclient12.1-basic-12.1.0.2.0-1.x86_64.rpm \
	oracle-instantclient12.1-devel-12.1.0.2.0-1.x86_64.rpm
export LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib:$LD_LIBRARY_PATH
export PATH=/usr/lib/oracle/12.1/client64/bin:$PATH
logout
eb deploy
```

The deploy will succeed, but pointing a browser to the app URL returns HTTP 500. To fix this, move the secrets file to the correct place on the server:

```Shell
scp \
	db-secrets.json \
	ec2-user@YOUR.EC2.DOMAIN.NAME:~
eb ssh
sudo mv db-secrets.json /opt/python/current/app
logout
eb open
```
