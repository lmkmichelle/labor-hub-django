FROM node:20-slim AS node-builder

WORKDIR /app

COPY package.json ./
RUN npm install

# Tailwind v4 is CSS-first (config lives in static/src/input.css); there are no
# tailwind.config.js / postcss.config.js files to copy.
COPY ./static ./static
COPY ./templates ./templates

RUN npm run build

FROM python:3.12.11-slim-bullseye

RUN mkdir /app
WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# upgrade pip
RUN pip install --upgrade pip

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Django project to the container
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh


# Expose the Django port
EXPOSE 8000
COPY . .

# Use the CSS compiled in the node stage, overriding any stale committed copy.
COPY --from=node-builder /app/static/src/output.css ./static/src/output.css

# Dev server via entrypoint (migrate + runserver). For production, use gunicorn:
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "nole.wsgi:application"]
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
