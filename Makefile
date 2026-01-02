# === TeriMedi Makefile ===
.PHONY: build up down restart reset migrate clean
# Redémarrer docker

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down



migrate:
	docker compose exec web python manage.py makemigrations
	docker compose exec web python manage.py migrate

clean:
	docker system prune -af --volumes

restart:
	docker compose down
	 
	docker compose up -d

build: ## Construire l'image Docker
	docker-compose build

up: ## Démarrer tous les services (PostgreSQL + Redis)
	docker-compose up -d

##down: ## Arrêter tous les services
##docker-compose down

logs: ## Afficher les logs
	docker-compose logs -f

clean: ## Nettoyer les conteneurs et volumes
	docker-compose down -v
	docker system prune -f

rebuild: clean build up ## Reconstruire et redémarrer


simple-down: ## Arrêter la version simple
	docker-compose -f docker-compose.simple.yml down

# Créer un superuser
superuser:
	docker-compose exec web python manage.py createsuperuser
	
simple-logs: ## Logs de la version simple
	docker-compose -f docker-compose.simple.yml logs -f

dev-local: ## Développement local sans Docker
	docker compose exec web python manage.py runserver

# Test API
test:
	docker compose exec web python manage.py test

# Accéder au conteneur
#ctn:
#docker compose exec web bash
	
shell: ## Ouvrir le shell Django
	python manage.py shell

# Nettoyer les volumes (attention: supprime les données)
clean:
	docker compose down -v
	docker system prune -f
