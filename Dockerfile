FROM tiangolo/uwsgi-nginx-flask:python3.7

ENV ORACLE_HOME /opt/oracle/instantclient_19_3
ENV LD_RUN_PATH=$ORACLE_HOME
ENV LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
ENV PATH=/opt/oracle/instantclient_19_3:$PATH

COPY instantclient/* /tmp/
COPY . /app

RUN apt-get update && apt-get install -y libaio1

RUN \
	mkdir -p /opt/oracle && \
	unzip "/tmp/instantclient*.zip" -d /opt/oracle && \
	# ln -s $ORACLE_HOME/libclntsh.so.19.3 $ORACLE_HOME/libclntsh.so && \
	pip install -r requirements.txt
