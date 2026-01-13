FROM python:3.12.11-slim-bullseye

RUN mkdir /app
WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y netcat build-essential libjpeg-dev zlib1g-dev python3-tk

# install psycopg2 dependencies
RUN pip install --upgrade pip

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Django project to the container
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh


# Expose the Django port
EXPOSE 8000
COPY . .
# Run Django’s development server
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "nole.wsgi:application"]
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
