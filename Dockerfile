FROM python:3.9-slim-buster

WORKDIR /usr/src/app


RUN python -m venv venv
ENV PATH="/usr/src/app/venv/bin:$PATH"

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install curl -y


EXPOSE 8000

CMD ["sh","-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]