FROM docker.io/python:3.11.3

ARG BASE_DIR=/opt/app

ENV \
    # python
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # poetry
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.5.1 python3 -
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR ${BASE_DIR}
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --no-ansi

WORKDIR ${BASE_DIR}/src
ENV PYTHONPATH "$PYTHONPATH:${BASE_DIR}/src/:${BASE_DIR}/src/.contrib-candidates"

COPY ./src ./

ENV \
    DJANGO_SETTINGS_MODULE=project.settings \
    PORT=80

EXPOSE 80/tcp
VOLUME ["/media"]

RUN \
    DJ__SECRET_KEY=empty \
    POSTGRES_DSN=postgres://user:password@db:5432/not-exist \
    WEBAPP_ROOT_URL=http://example.org/ \
    TG__BOT_TOKEN=999 \
    ./manage.py collectstatic --noinput

CMD gunicorn project.wsgi:application --access-logfile -
