FROM python:3.10-slim

RUN apt update -y && apt install -y python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY pyproject.toml /app
RUN pip install --no-cache-dir .[mdimport]

COPY src/ /app/src
RUN pip install --no-deps .[mdimport]

ENTRYPOINT ["python"]
CMD ["-m", "vccmdimport", "main"]