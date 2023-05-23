FROM python:3.9-slim-buster

WORKDIR /usr/src/app


RUN python -m venv venv
ENV PATH="/usr/src/app/venv/bin:$PATH"

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install curl -y
RUN apt-get install -y git
RUN apt-get purge -y --auto-remove
RUN rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/SciCatProject/pyscicat.git /usr/src/app/pyscicat_repo \
    && cd /usr/src/app/pyscicat_repo \
    && git pull origin \
    && git checkout v4.x \
    && cp -Rf pyscicat ../.


EXPOSE 8000

CMD ["sh","-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]
