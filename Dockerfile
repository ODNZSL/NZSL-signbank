FROM node:lts AS node

WORKDIR /app
ADD ./signbank/static signbank/static
ADD package.json /app

ADD package-lock.json /app

RUN npm ci &&\
    npm run collectjs &&\
    npm run collectcss

FROM python:3.9

ENV DJANGO_SETTINGS_MODULE=signbank.settings.development

RUN pip install "poetry==2.1.1"

CMD bin/develop.py migrate --noinput && \
    bin/develop.py createcachetable && \
    (\
        (test $DJANGO_SETTINGS_MODULE = 'signbank.settings.development' && \
        echo "Loading initial content pages..." && \
        bin/develop.py loaddata signbank/contentpages/fixtures/flatpages_initial_data.json) \
    || echo "Skipping loading initial content pages") &&\
    bin/develop.py createinitialrevisions &&\
    gunicorn signbank.wsgi --bind=0.0.0.0:${PORT:=8000}

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

RUN echo "APT::Install-Recommends \"0\";" >> /etc/apt/apt.conf.d/02recommends && \
    echo "APT::Install-Suggests \"0\";" >> /etc/apt/apt.conf.d/02recommends && \
    apt-get -qq update && \
    apt-get -qq install \
        build-essential \
        postgresql-client \
        && \
    rm -rf /var/lib/apt/lists/* && \
    true

# Install requirements
WORKDIR /app
ADD pyproject.toml poetry.lock /app/

COPY vendor/ /app/vendor/
RUN cd /app/vendor/django-tagging-patches && ./patch.sh


RUN poetry config installer.max-workers 10 && \
    poetry config virtualenvs.create false &&  \
    poetry install -v --no-root

# Copy frontend assets
COPY --from=node /app/signbank/static/js ./signbank/static/js
COPY --from=node /app/signbank/static/css ./signbank/static/css

# Install application
ADD . /app

# Collect static assets
RUN bin/develop.py collectstatic --no-input
