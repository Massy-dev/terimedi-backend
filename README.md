
=======
# TeriMedi Backend API

API backend pour la plateforme TeriMedi - Service de livraison de médicaments.

## 🚀 Fonctionnalités

- **Authentification JWT** avec rôles (client, pharmacien)
- **Gestion des pharmacies** avec géolocalisation
- **Système de commandes** avec relance automatique
- **Notifications en temps réel** via WebSocket et FCM
- **API REST** documentée avec Swagger
- **Tâches asynchrones** avec Celery
- **Base de données géospatiale** PostgreSQL/PostGIS

## 🛠️ Technologies

- **Django 5.2** + Django REST Framework
- **PostgreSQL** + PostGIS pour la géolocalisation
- **Redis** pour le cache et les tâches
- **Celery** pour les tâches asynchrones
- **Channels** pour les WebSockets
- **Docker** pour la conteneurisation

## 📋 Prérequis

- Docker et Docker Compose
- Python 3.11+
- GDAL (pour le développement local)

## 🚀 Installation

### 1. Cloner le projet
```bash
git clone <repository-url>
cd terimedi-backend-api
```

### 2. Configuration des variables d'environnement
```bash
cp env.example .env
# Éditer .env avec vos valeurs
```

### 3. Démarrer les services
```bash
# Démarrer tous les services
make up

# Ou manuellement
docker-compose up --build
```

### 4. Appliquer les migrations
```bash
make migrate
```

### 5. Créer un superuser
```bash
make superuser
```

## 🔧 Configuration

### Variables d'environnement obligatoires

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
POSTGRES_DB=terimedi
POSTGRES_USER=teri_user
POSTGRES_PASSWORD=teri_pass
```

### Variables optionnelles

```env
FCM_SERVER_KEY=your-fcm-key
DEFAULT_FROM_EMAIL=no-reply@terimedi.local
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## 📚 API Endpoints

### Authentification
- `POST /api/token/` - Obtenir un token JWT
- `POST /api/token/refresh/` - Rafraîchir un token
- `POST /api/users/register/` - Inscription utilisateur
- `POST /api/users/login/` - Connexion utilisateur

### Pharmacies
- `GET /api/pharmacies/` - Liste des pharmacies
- `GET /api/pharmacies/pharmacies/nearby/` - Pharmacies à proximité
- `POST /api/pharmacies/device-token/` - Enregistrer token FCM

### Commandes
- `GET /api/orders/commandes/` - Liste des commandes
- `POST /api/orders/commandes/` - Créer une commande
- `PATCH /api/orders/commandes/{id}/changer-statut/` - Changer le statut

### Documentation
- `/swagger/` - Documentation Swagger
- `/redoc/` - Documentation ReDoc

## 🧪 Tests

```bash
# Lancer tous les tests
make test

# Tests spécifiques
docker-compose exec web python manage.py test apps.users
docker-compose exec web python manage.py test apps.pharmacies
```

## 🐳 Commandes Docker utiles

```bash
# Démarrer les services
make up

# Arrêter les services
make down

# Redémarrer
make restart

# Voir les logs
make logs

# Accéder au shell
make shell

# Recréer les migrations
make migrations
```

## 🔍 Structure du projet

```
terimedi-backend-api/
├── apps/
│   ├── users/           # Gestion des utilisateurs
│   ├── pharmacies/      # Gestion des pharmacies
│   ├── orders/          # Gestion des commandes
│   └── notifications/   # Système de notifications
├── config/              # Configuration Django
├── requirements/         # Dépendances Python
├── docker-compose.yml   # Services Docker
└── Dockerfile          # Image Docker
```

## 🚨 Dépannage

### Problème de connexion à la base de données
```bash
# Vérifier que PostgreSQL est démarré
docker-compose ps db

# Vérifier les logs
docker-compose logs db
```

### Problème de Redis
```bash
# Redémarrer Redis
docker-compose restart redis

# Vérifier la connexion
docker-compose exec redis redis-cli ping
```

### Problème de Celery
```bash
# Vérifier les workers
docker-compose ps celery

# Voir les logs
docker-compose logs celery
```

## 📝 Développement

### Ajouter une nouvelle app
```bash
docker-compose exec web python manage.py startapp myapp
```

### Créer des migrations
```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

### Shell Django
```bash
docker-compose exec web python manage.py shell
```

## 🔒 Sécurité

- **CORS** configuré pour limiter l'accès
- **JWT** avec rotation des tokens
- **Validation** des données d'entrée
- **Permissions** par rôle utilisateur
- **HTTPS** recommandé en production

## 📄 Licence

Ce projet est sous licence propriétaire.

## 🤝 Support

Pour toute question ou problème, contactez l'équipe de développement.

Meité Yakouba
🧠 Dev Backend & Data Enthusiast
📫 https://www.linkedin.com/in/yakouba-meite-951b5914a/
>>>>>>> d36a812 (Backend: orders workflow, WebSocket notifications (Phase 1))
