FROM redmine:4.2

RUN apt-get update && \
    apt-get install -y libpcre2-8-0 && \
    rm -rf /var/lib/apt/lists/*

COPY docker_redmine/flatly_light_redmine-master /usr/src/redmine/public/themes/flatly_light_redmine-master
