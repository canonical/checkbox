#!/bin/sh
# Requires activated virtualenv with coverage
coverage run --branch setup.py test && coverage report ; coverage html
