FROM python:3.10-slim

WORKDIR /app

ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y tzdata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY . .
RUN pip install --no-cache-dir -r requirements.txt


ENV OPENAI_KEY=""
ENV OPENAI_BASE_URL=""

EXPOSE 23333

CMD ["python", "web/app.py"] 

