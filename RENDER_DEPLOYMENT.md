# 🌐 Render Deployment Guide

## 🚀 Deploy to Render (Step by Step)

### **Step 1: Prepare Repository**

1. **Push to GitHub** (if not already done):
```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

2. **Verify files are present**:
   - ✅ `Dockerfile`
   - ✅ `docker-compose.prod.yml`
   - ✅ `build.sh`
   - ✅ `requirements.txt`
   - ✅ `render.yaml`

### **Step 2: Create Render Account**

1. Go to [render.com](https://render.com)
2. Sign up with GitHub account
3. Connect your GitHub repository

### **Step 3: Create PostgreSQL Database**

1. **In Render Dashboard**:
   - Click "New +" → "PostgreSQL"
   - Name: `mess-management-db`
   - Database: `mess_management`
   - User: `postgres`
   - Region: Choose closest to your users
   - Plan: **Free** (for testing) or **Starter** (for production)

2. **Copy Connection Details**:
   - Internal Database URL (for Docker)
   - External Database URL (for local testing)

### **Step 4: Create Redis Instance**

**⚠️ Important**: Render doesn't offer Redis as a separate service in free tier.

**Option A: Use External Redis (Recommended)**
1. **Upstash Redis** (Free tier available):
   - Go to [upstash.com](https://upstash.com)
   - Create free Redis database
   - Copy Redis URL: `redis://default:password@host:port`

**Option B: Use Redis Labs**
1. **Redis Cloud** (Free tier available):
   - Go to [redis.com](https://redis.com/try-free/)
   - Create free database
   - Copy connection string

**Option C: Disable Redis Features** (Simplest for testing)
- Set `REDIS_URL=` (empty) in environment variables
- Celery tasks will run synchronously

### **Step 5: Create Web Service**

1. **In Render Dashboard**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Name: `mess-management-system`

2. **Configure Build Settings**:
   
   **🔥 IMPORTANT: Choose "Docker" from the Language dropdown**
   
   ```
   Language: Docker (NOT Python)
   Build Command: (Leave empty - Render auto-detects Dockerfile)
   Start Command: (Leave empty - Uses Dockerfile CMD)
   ```
   
   **Note:** Render automatically detects and builds Docker containers. No custom build/start commands needed.
   
   **Why Docker instead of Python?**
   - Your app needs multiple services (Django + Celery + Telegram bot)
   - System dependencies (PostgreSQL client, image processing)
   - Background workers for payments and notifications

3. **Advanced Settings**:
   ```
   Port: 10000
   Health Check Path: /health/
   Auto-Deploy: Yes
   ```

### **Step 6: Environment Variables**

Add these environment variables in Render dashboard:

#### **Required Variables**
```bash
# Django Settings
DJANGO_SETTINGS_MODULE=mess_management.settings.production
SECRET_KEY=your-super-secret-production-key-32-chars-minimum
DEBUG=False
ALLOWED_HOSTS=your-app-name.onrender.com

# Database (from Step 3)
DATABASE_URL=postgresql://postgres:password@host:5432/mess_management

# Redis (from Step 4 - choose one option)
REDIS_URL=redis://default:password@host:port  # Upstash/Redis Labs
# OR leave empty to disable: REDIS_URL=

# Telegram Bot (REQUIRED - Get from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_TG_IDS=123456789,987654321

# Security
QR_SECRET=your-32-character-secret-for-qr-codes-here
STAFF_SCANNER_PASSWORD=your-secure-admin-password
```

#### **Optional Variables** (for full features)
```bash
# Cloudinary (for image storage)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Google Sheets (for backup logging)
SHEETS_CREDENTIALS_JSON={"type":"service_account",...}
SHEETS_SPREADSHEET_ID=your-spreadsheet-id

# Email (for notifications)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### **Step 7: Deploy**

1. **Click "Create Web Service"**
2. **Monitor Build Logs**:
   - Build takes 5-10 minutes
   - Watch for any errors
   - Wait for "Deploy succeeded" message

3. **Check Deployment**:
   - Visit your app URL: `https://your-app-name.onrender.com`
   - Check health endpoint: `https://your-app-name.onrender.com/health/`

### **Step 8: Initialize Database**

Once deployed, run these commands:

```bash
# Option 1: Using Render Shell (Recommended)
# Go to your service → Shell tab → Run commands:

python manage.py migrate
python manage.py createsuperuser
python manage.py setup_initial_data
python manage.py collectstatic --noinput
```

```bash
# Option 2: Using local connection
# Set DATABASE_URL to external URL and run locally:

export DATABASE_URL="postgresql://postgres:password@external-host:5432/mess_management"
python manage.py migrate
python manage.py createsuperuser
```

### **Step 9: Configure Background Services**

#### **Option A: Single Container (Simpler)**
Your current Dockerfile runs all services in one container:
- Web server (Gunicorn)
- Celery worker
- Telegram bot

This works for small to medium loads.

#### **Option B: Separate Services (Scalable)**
Create additional Render services:

1. **Background Worker**:
   ```
   Environment: Docker
   Build Command: docker build -t mess-worker .
   Start Command: docker run mess-worker celery -A mess_management worker -l info
   ```

2. **Telegram Bot Service**:
   ```
   Environment: Docker  
   Build Command: docker build -t mess-bot .
   Start Command: docker run mess-bot python manage.py run_telegram_bot
   ```

### **Step 10: Test Deployment**

1. **Web Interface**:
   - Visit your app URL
   - Login to admin panel
   - Test scanner interface

2. **API Endpoints**:
   ```bash
   curl https://your-app-name.onrender.com/health/
   curl https://your-app-name.onrender.com/api/v1/students/
   ```

3. **Telegram Bot**:
   - Message your bot
   - Test commands: `/start`, `/help`
   - Verify admin functions work

## 🔧 Production Configuration

### **Custom Domain** (Optional)
1. In Render dashboard → Settings → Custom Domains
2. Add your domain: `mess.yourdomain.com`
3. Update `ALLOWED_HOSTS` environment variable

### **SSL Certificate**
- Render provides free SSL automatically
- Your app will be available at `https://`

### **Monitoring**
1. **Render Metrics**: Built-in CPU, memory, response time
2. **Health Checks**: Automatic monitoring of `/health/` endpoint
3. **Log Streaming**: Real-time logs in dashboard

## 🐛 Troubleshooting

### **Build Failures**
```bash
# Common issues:
1. Missing Dockerfile → Check repository
2. Build timeout → Optimize Docker layers
3. Dependency errors → Check requirements.txt
```

### **Runtime Errors**
```bash
# Check logs in Render dashboard:
1. Application crashed → Check environment variables
2. Database connection → Verify DATABASE_URL
3. Static files missing → Run collectstatic
```

### **Telegram Bot Issues**
```bash
# Verify bot configuration:
1. Check TELEGRAM_BOT_TOKEN is correct
2. Verify bot is started: /start command
3. Check admin IDs in ADMIN_TG_IDS
```

## 💰 Cost Estimation

### **Free Tier** (Good for testing):
- Web Service: Free (with limitations)
- PostgreSQL: Free (1GB storage)
- Redis: Free (25MB)
- **Total: $0/month**

### **Production Tier**:
- Web Service: $7/month (Starter)
- PostgreSQL: $7/month (Starter - 1GB)
- Redis: $7/month (Starter - 1GB)
- **Total: ~$21/month**

## 🚀 Go Live Checklist

- [ ] Repository pushed to GitHub
- [ ] PostgreSQL database created
- [ ] Redis instance created
- [ ] Web service deployed successfully
- [ ] Environment variables configured
- [ ] Database migrations run
- [ ] Superuser created
- [ ] Static files collected
- [ ] Telegram bot working
- [ ] Health check passing
- [ ] Admin panel accessible
- [ ] Scanner interface working
- [ ] API endpoints responding

## 🔄 Updates & Maintenance

### **Deploy Updates**:
```bash
# Push changes to GitHub
git add .
git commit -m "Update feature"
git push origin main

# Render auto-deploys from main branch
```

### **Database Backups**:
- Render PostgreSQL includes automatic backups
- Use management command for custom backups:
```bash
python manage.py backup_data
```

### **Monitoring**:
- Check Render dashboard regularly
- Monitor application logs
- Set up alerts for downtime

Your mess management system is now ready for production deployment on Render! 🎉
