FROM python:2.7
ENV PYTHONUNBUFFERED 1

# Make a location for all of our stuff to go into
#RUN mkdir /code
RUN mkdir /opt/turbomachinery

# Set the working directory to this new location
#WORKDIR /code
WORKDIR /opt/turbomachinery

# Copy all of our scripts into the location
ADD requirements.txt /opt/turbomachinery/

# Install requirements for Django
RUN pip install -r requirements.txt

# Add our Django code
#ADD . /code/

# Expose the port so we can access Django as it's running
EXPOSE 8000

#RUN apt-get update
#RUN apt-get install -y texlive-latex-base

# Set the entry point script
#ADD docker_django/wait_for_postgres.sh /code/
#ADD docker_django/wait_for_postgres.py /code/
#RUN chmod +x /code/docker_django/wait_for_postgres.sh

ENTRYPOINT ["/opt/turbomachinery/docker_django/wait_for_postgres.sh"]

# Start the server:
#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["gunicorn", "--chdir", "/opt/turbomachinery/", "--bind", ":8000", "pr.wsgi:application"]
