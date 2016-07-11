WD=$(shell pwd)

env:
	virtualenv env
	env/bin/pip install -r requirements.txt

help:
	@env/bin/python desjardins.py || true
