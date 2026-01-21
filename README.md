### Getting Started

```
npm install
npx @tailwindcss/cli -i ./static/src/input.css -o ./static/src/output.css --watch
docker compose up --build
```

### Applying Migrations

```
docker exec -it nole-app python manage.py makemigrations    
docker exec -it nole-app python manage.py migrate
```
### Make new app
```
docker exec -it nole-app python manage.py startapp <app_name>
```
