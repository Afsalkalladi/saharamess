# 🍽️ Mess Management System

A comprehensive digital mess management solution with Telegram bot integration and QR-based meal access control.

## Quick Start

1. **Setup project:**
   ```bash
   source venv/bin/activate
   make setup
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start development:**
   ```bash
   make dev
   ```

## Project Structure

```
mess-management-system/
├── core/                   # Main application logic
├── scanner/               # QR scanner interface
├── admin_panel/           # Admin dashboard
├── api/                   # REST API
└── docker/                # Docker configuration
```

## Features

- 🤖 Telegram bot for student interactions
- 📱 Mobile QR scanner for staff
- ⚙️ Admin panel for management
- 📊 Real-time reports and analytics
- 🔒 Secure QR code authentication
- ☁️ Cloud backup with Google Sheets

## Documentation

- [API Documentation](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Development Guide](docs/DEVELOPMENT.md)

## Support

For support, create an issue or contact the development team.
