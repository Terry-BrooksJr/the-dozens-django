#!/usr/bin/env bash

cd $"{HOME}"

gunicorn --workers=2  --threads=2 thedozens.wsgi:application -b :8080