FROM python:3.6-slim-stretch

RUN apt-get update && apt-get install -y \
            gcc \
            libldap2-dev \
            libsasl2-dev \
            libssl-dev

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY . /src

WORKDIR /src
CMD ["/usr/local/bin/gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "--pythonpath=/src", "steward.wsgi"]
