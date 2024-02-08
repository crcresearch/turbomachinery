#!/bin/sh

# wait until Postgres is ready
while ! python /code/docker_django/wait_for_postgres.py localhost; do
  echo "$(date) - waiting for Postgres..."
  sleep 1
done