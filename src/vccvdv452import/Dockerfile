FROM python:3.10-slim

RUN apt update -y && apt install -y git python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY .git/ /app/.git
RUN mkdir -p /app/src/vcclib/

COPY pyproject.toml /app
RUN pip install --no-cache-dir .[vdv452import]

COPY src/ /app/src
RUN pip install --no-deps .[vdv452import]

ENTRYPOINT ["python"]
CMD ["-m", "vccvdv452import", "main"]