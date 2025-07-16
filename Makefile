# === TeriMedi Makefile ===

# Démarrer les containers
up:
	docker-compose up --build

# Stopper les containers
down:
	docker-compose down

# Recréer les migrations
migrations:
	docker-compose exec web python manage.py makemigrations

# Appliquer les migrations
migrate:
	docker-compose exec web python manage.py migrate

# Créer un superuser
superuser:
	docker-compose exec web python manage.py createsuperuser

# Voir les logs du conteneur web
logs:
	docker-compose logs -f web

# Lancer un shell Django
shell:
	docker-compose exec web python manage.py shell

# Test API (à venir)
test:
	docker-compose exec web python manage.py test
