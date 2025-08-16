# 🍽️ Mess Management System

A comprehensive digital mess management solution with Telegram bot integration and QR-based meal access control.

## 🚀 Features

### For Students
- **Telegram Bot Interface**: Complete registration and management via Telegram
- **QR Code Access**: Permanent QR codes for meal access
- **Payment Management**: Upload payment screenshots for verification
- **Mess Cut Applications**: Apply for mess cuts with automatic cutoff enforcement
- **Real-time Notifications**: Get notified for all important events

### For Staff
- **Mobile QR Scanner**: Web-based QR scanner for meal verification
- **Offline Support**: Continue scanning even with poor connectivity
- **Student Information**: View student details, payment status, and access rights
- **Multiple Meal Types**: Support for breakfast, lunch, and dinner

### For Admins
- **Telegram Admin Panel**: Approve registrations, verify payments, manage closures
- **Comprehensive Reports**: Payment status, mess cuts, and usage analytics
- **Audit Trail**: Complete logging of all system activities
- **Google Sheets Backup**: Automatic backup of critical data
- **QR Code Management**: Regenerate all QR codes when needed

## 🏗️ Architecture

```mermaid
flowchart LR
    TG[Telegram Users/Admin] -->|Webhook| DJ[Django + DRF]
    ST[Staff Scanner Web] --> DJ
    DJ <-->|PostgreSQL| DB[(Database)]
    DJ --> CL[Cloudinary]
    DJ --> GS[Google Sheets API]
    DJ --> WK[Celery Worker]
    CR[Celery Beat] --> DJ
    RD[Redis] --> WK
    RD --> CR
```

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (optional)
- Telegram Bot Token
- Cloudinary Account
- Google Sheets API Credentials

## 🛠️ Installation

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mess-management-system.git
   cd mess-management-system
   ```

2. **Copy environment variables**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**
   Edit `.env` file with your credentials:
   ```bash
   # Required configurations
   TELEGRAM_BOT_TOKEN=your_bot_token
   ADMIN_TG_IDS=your_telegram_id
   CLOUDINARY_URL=your_cloudinary_url
   SHEETS_CREDENTIALS_JSON=your_service_account_json
   QR_SECRET=your_secret_key
   ```

4. **Start the services**
   ```bash
   docker-compose up -d
   ```

5. **Run initial setup**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   docker-compose exec web python manage.py collectstatic --noinput
   ```

### Manual Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure PostgreSQL and Redis**
   ```bash
   # Create database
   createdb mess_management
   
   # Start Redis
   redis-server
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Start services**
   ```bash
   # Terminal 1: Web server
   python manage.py runserver
   
   # Terminal 2: Celery worker
   celery -A mess_management worker --loglevel=info
   
   # Terminal 3: Celery beat
   celery -A mess_management beat --loglevel=info
   
   # Terminal 4: Telegram bot
   python manage.py run_telegram_bot --polling
   ```

## ⚙️ Configuration

### Telegram Bot Setup

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your bot token
3. Set webhook URL (production) or use polling (development)
4. Add your Telegram ID to `ADMIN_TG_IDS`

### Google Sheets Setup

1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a service account and download credentials
4. Create a spreadsheet and share it with the service account email
5. Add the spreadsheet ID to environment variables

### QR Scanner Access

1. Visit `/scanner/login` 
2. Enter admin password
3. Generate staff tokens with appropriate validity
4. Share scanner URLs with staff

## 📱 Usage

### Student Registration Flow

```mermaid
sequenceDiagram
    participant S as Student
    participant B as Bot
    participant A as Admin
    
    S->>B: /start → Register
    B->>A: New registration notification
    A->>B: Approve/Deny
    B->>S: Approval + QR Code
```

### Payment Upload Flow

```mermaid
sequenceDiagram
    participant S as Student
    participant B as Bot
    participant A as Admin
    participant C as Cloudinary
    
    S->>B: Upload Payment
    B->>C: Store screenshot
    B->>A: Payment review notification
    A->>B: Verify/Deny
    B->>S: Verification result
```

### Meal Access Flow

```mermaid
sequenceDiagram
    participant ST as Staff
    participant S as Scanner
    participant API as Backend
    participant STU as Student
    
    ST->>S: Scan QR Code
    S->>API: Verify access
    API->>S: Student info + Access result
    S->>STU: Notification (if allowed)
```

## 🔒 Security Features

- **HMAC-signed QR codes** with versioning support
- **Staff token authentication** with expiration
- **Admin role-based access** via Telegram ID verification
- **Input validation** at all API endpoints
- **Audit logging** for all critical operations
- **Rate limiting** and DDoS protection ready

## 📊 Business Rules

### Mess Cut Rules
- Can only apply for **tomorrow onwards** until **11:00 PM today**
- No same-day or backdated cuts allowed
- Automatic overlap handling with mess closures

### Payment Validation
- Screenshot upload to Cloudinary
- Admin manual verification required
- Cycle-based validity checking
- Offline manual payment marking

### Access Control
- Student must be **approved**
- Valid payment for current cycle required
- No active mess cut for the day
- Mess not closed for the day

## 🔧 API Endpoints

### Public Endpoints
- `POST /api/v1/scanner/scan` - QR code scanning
- `POST /telegram/webhook` - Telegram webhook

### Admin Endpoints
- `GET /api/v1/students/` - List students
- `POST /api/v1/students/{id}/approve` - Approve student
- `GET /api/v1/payments/` - List payments
- `POST /api/v1/payments/{id}/verify` - Verify payment
- `POST /api/v1/admin/qr/regenerate-all` - Regenerate QR codes

### Reports
- `GET /api/v1/admin/reports/payments` - Payment reports
- `GET /api/v1/admin/reports/mess-cuts` - Mess cut reports

## 🧪 Testing

```bash
# Run tests
python manage.py test

# Run with coverage
coverage run --source='.' manage.py test
coverage report

# Load test data
python manage.py loaddata fixtures/test_data.json
```

## 📦 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure HTTPS and SSL certificates
- [ ] Set up proper database with connection pooling
- [ ] Configure Redis for production
- [ ] Set up monitoring (Sentry, logging)
- [ ] Configure backup strategy
- [ ] Set up domain and DNS
- [ ] Configure Telegram webhook
- [ ] Test all functionality end-to-end

### Environment Variables for Production

```bash
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:pass@db:5432/mess_management
REDIS_URL=redis://redis:6379/0
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
SECURE_SSL_REDIRECT=True
```

## 📈 Monitoring

### Health Checks
- `/api/v1/health/` - Application health
- Database connectivity
- Redis connectivity
- Telegram bot status

### Metrics
- Registration approval rate
- Payment verification time
- Scan success rate
- Meal utilization statistics

## 🔄 Backup & Recovery

### Automated Backups
- **Google Sheets**: Real-time backup of critical events
- **Database**: Daily PostgreSQL dumps
- **Media Files**: Cloudinary automatic backup

### DLQ (Dead Letter Queue)
- Failed Google Sheets operations are queued for retry
- Automatic retry with exponential backoff
- Manual recovery tools available

## 🆘 Troubleshooting

### Common Issues

**Bot not responding**
```bash
# Check bot status
docker-compose logs telegram-bot
```

**QR codes not working**
```bash
# Regenerate all QR codes
curl -X POST http://localhost:8000/api/v1/admin/qr/regenerate-all
```

**Payment upload fails**
- Check Cloudinary configuration
- Verify file size limits
- Check network connectivity

### Logs
```bash
# View application logs
docker-compose logs web

# View worker logs  
docker-compose logs worker

# View all logs
docker-compose logs -f
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Django REST Framework team
- python-telegram-bot library
- QR Scanner JavaScript library
- All contributors and testers

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Contact the development team
- Check the documentation wiki

---

**Built with ❤️ for efficient mess management**