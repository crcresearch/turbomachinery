# define an alias for the specific python version used in this file.
FROM python:3.11.5-slim-bullseye as python
FROM python as python-build-stage
ENV PYTHONUNBUFFERED 1

RUN mkdir /code
WORKDIR /code

ADD requirements.txt /code/

# RUN apt-get update && apt-get install --no-install-recommends -y \
#   build-essential \
#   libpq-dev

# RUN pip wheel --wheel-dir /usr/src/app/wheels -r requirements.txt
# RUN pip install --no-index --find-links=/usr/src/app/wheels -r requirements.txt

# ADD . /code/

# EXPOSE 8000

# COPY docker_django/wait_for_postgres.py /code/docker_django/
# ADD docker_django/wait_for_postgres.sh /code/

# RUN chmod +x /code/docker_django/wait_for_postgres.sh
# RUN chmod +x /code/docker_django/wait_for_postgres.py



# ENTRYPOINT ["/code/docker_django/wait_for_postgres.sh"]
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
RUN apt-get update && apt-get install --no-install-recommends -y \
  build-essential \
  libpq-dev

RUN pip wheel --wheel-dir /usr/src/app/wheels -r requirements.txt
RUN pip install --no-index --find-links=/usr/src/app/wheels -r requirements.txt

ADD . /code/

EXPOSE 8000

COPY docker_django/wait_for_postgres.py /code/docker_django/
ADD docker_django/wait_for_postgres.sh /code/docker_django/

RUN chmod +x /code/docker_django/wait_for_postgres.sh
RUN chmod +x /code/docker_django/wait_for_postgres.py

ENTRYPOINT ["/code/docker_django/wait_for_postgres.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]