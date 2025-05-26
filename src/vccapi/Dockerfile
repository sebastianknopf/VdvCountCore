FROM python:3.10-slim

RUN apt update -y && apt install -y python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY pyproject.toml /app
RUN pip install --no-cache-dir .[api]

COPY src/ /app/src
RUN pip install --no-deps .[api]

EXPOSE 8080

ENTRYPOINT ["python"]
CMD ["-m", "uvicorn", "src.vccapi.api:app", "--port", "8080", "--host", "0.0.0.0"]