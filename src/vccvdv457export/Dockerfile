FROM python:3.10-slim

RUN apt update -y && apt install -y git python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY .git/ /app/.git
RUN mkdir -p /app/src/vcclib/

COPY pyproject.toml /app
RUN pip install --no-cache-dir .[vdv457export]

COPY src/ /app/src
RUN pip install --no-deps .[vdv457export]

ENTRYPOINT ["python"]
CMD ["-m", "vccvdv457export", "main"]