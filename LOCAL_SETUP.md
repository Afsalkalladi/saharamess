# 🏠 Local Development Setup Guide

## 🚀 Quick Start (5 minutes)

### **Prerequisites**
- Docker Desktop installed
- Git installed
- Text editor (VS Code recommended)

### **Step 1: Clone & Setup**
```bash
# Clone repository
git clone https://github.com/Afsalkalladi/saharamess.git
cd saharamess

# Copy environment file
cp .env.example .env.development
```

### **Step 2: Configure Environment**
Edit `.env.development` with your values:

```bash
# Required: Get Telegram Bot Token
# 1. Message @BotFather on Telegram
# 2. Create new bot: /newbot
# 3. Copy token to TELEGRAM_BOT_TOKEN

# Required: Get your Telegram ID
# 1. Message @userinfobot on Telegram
# 2. Copy your ID to ADMIN_TG_IDS

TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_TG_IDS=123456789
```

### **Step 3: Start Services**
```bash
# Start all services (PostgreSQL, Redis, Django, Celery, Bot)
docker-compose up -d

# View logs
docker-compose logs -f
```

### **Step 4: Initialize Database**
```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Load initial data
docker-compose exec web python manage.py setup_initial_data
```

### **Step 5: Access Application**
- **Web App**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Scanner**: http://localhost:8000/scanner
- **API**: http://localhost:8000/api/v1

## 🔧 Development Commands

### **Service Management**
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart specific service
docker-compose restart web

# View logs
docker-compose logs -f web
docker-compose logs -f telegram-bot
```

### **Database Operations**
```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create migrations
docker-compose exec web python manage.py makemigrations

# Reset database
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate
```

### **Django Management**
```bash
# Django shell
docker-compose exec web python manage.py shell

# Collect static files
docker-compose exec web python manage.py collectstatic

# Run tests
docker-compose exec web python manage.py test
```

### **Custom Commands**
```bash
# Generate QR codes
docker-compose exec web python manage.py generate_qr_codes

# Backup data
docker-compose exec web python manage.py backup_data

# Cleanup old data
docker-compose exec web python manage.py cleanup_old_data
```

## 🐛 Troubleshooting

### **Common Issues**

**1. Port Already in Use**
```bash
# Check what's using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use port 8001 instead
```

**2. Database Connection Error**
```bash
# Check database status
docker-compose ps

# Restart database
docker-compose restart db

# View database logs
docker-compose logs db
```

**3. Telegram Bot Not Working**
```bash
# Check bot logs
docker-compose logs telegram-bot

# Test bot token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

**4. Permission Errors**
```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📱 Testing the Application

### **1. Test Web Interface**
- Visit http://localhost:8000
- Login with superuser credentials
- Navigate through admin panel

### **2. Test Scanner**
- Go to http://localhost:8000/scanner
- Use staff password from `.env.development`
- Test QR code scanning

### **3. Test Telegram Bot**
- Message your bot on Telegram
- Try commands: `/start`, `/help`, `/status`
- Test admin commands if you're admin

### **4. Test API**
```bash
# Health check
curl http://localhost:8000/health/

# API endpoints
curl http://localhost:8000/api/v1/students/
curl http://localhost:8000/api/v1/payments/
```

## 🔄 Development Workflow

### **Making Changes**
```bash
# 1. Make code changes
# 2. Restart affected service
docker-compose restart web

# 3. View logs
docker-compose logs -f web

# 4. Test changes
# 5. Commit changes
git add .
git commit -m "Your changes"
```

### **Database Changes**
```bash
# 1. Modify models
# 2. Create migrations
docker-compose exec web python manage.py makemigrations

# 3. Apply migrations
docker-compose exec web python manage.py migrate

# 4. Test changes
```

## 📊 Monitoring

### **Service Status**
```bash
# Check all services
docker-compose ps

# Resource usage
docker stats

# Service health
curl http://localhost:8000/health/
```

### **Logs**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f telegram-bot
docker-compose logs -f worker
```

## 🎯 Next Steps

Once local development is working:
1. Test all features thoroughly
2. Configure production environment variables
3. Deploy to Render
4. Set up monitoring and backups
