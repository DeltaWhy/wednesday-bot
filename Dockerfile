FROM python:3.9
RUN mkdir /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY . /app

VOLUME /data
ENV DB_FILE=/data/wednesday-bot.db
CMD python main.py
