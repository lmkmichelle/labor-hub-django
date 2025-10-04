### Getting Started

```
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
