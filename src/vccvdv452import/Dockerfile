FROM python:3.10-slim

RUN apt update -y && apt install -y python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .[vdv452import]

ENTRYPOINT ["python"]
CMD ["-m", "vccvdv452import", "main"]