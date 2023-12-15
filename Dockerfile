FROM tiangolo/uwsgi-nginx-flask:python3.11

COPY . /app

RUN \
	pip install -r requirements.txt
