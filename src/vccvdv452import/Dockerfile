FROM python:3.10-slim

RUN apt update -y && apt install -y python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY pyproject.toml /app
RUN pip install --no-cache-dir .[vdv452import]

COPY .env /app
COPY .env.dev /app
COPY docker-compose.yaml /app
COPY docker-compose.dev.yaml /app

COPY src/ /app/src
RUN pip install --no-deps .[vdv452import]

ENTRYPOINT ["python"]
CMD ["-m", "vccvdv452import", "main"]