FROM python:3.10-slim

RUN apt update -y && apt install -y python3-dev default-libmysqlclient-dev pkg-config build-essential

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .[api]

EXPOSE 8080

ENTRYPOINT ["python"]
CMD ["-m", "uvicorn", "src.vccapi.api:app", "--port", "8080", "--host", "0.0.0.0"]