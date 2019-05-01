FROM python:3.7.3-slim-stretch

ARG VERSION=0.0.0
LABEL maintainer="Caleb Hattingh <caleb.hattingh@gmail.com>"
LABEL version=$VERSION

COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . /venus
WORKDIR /venus
RUN pip install -e .
CMD ["venus"]
