# Deployment Guide

This guide covers deploying the IBKR AI Trading Agent to GitHub and Coolify.

## Prerequisites

- GitHub account with access to: https://github.com/megadoom99/trading
- Coolify instance set up and running
- OpenRouter API key (required)
- Finnhub API key (optional)
- Interactive Brokers account with TWS/IB Gateway (for trading functionality)

---

## Part 1: Push to GitHub

### Option A: Using Replit Git Pane (Recommended)

1. **Open Git Pane** in Replit (left sidebar)
2. **Stage all files** - Click the "+" icon next to changed files
3. **Commit changes**:
   - Enter commit message: "Initial commit - IBKR trading app"
   - Click "Commit & push"
4. **Set remote** (if not already set):
   ```bash
   git remote add origin https://github.com/megadoom99/trading.git
   ```
5. **Push to GitHub**:
   - Click "Push" in the Git pane
   - Or use the terminal: `git push -u origin main`

### Option B: Using Terminal

```bash
# Add all files
git add .

# Commit
git commit -m "Initial commit - IBKR trading app"

# Add remote (if not already added)
git remote add origin https://github.com/megadoom99/trading.git

# Push to GitHub
git push -u origin main
```

**Note:** Make sure `.env` file is NOT pushed (it's in `.gitignore` for security).

---

## Part 2: Deploy to Coolify

### Step 1: Create New Application

1. **Log into Coolify** dashboard
2. **Create Resource** → Select "Application"
3. **Connect GitHub Repository**:
   - Select your GitHub account
   - Choose repository: `megadoom99/trading`
   - Branch: `main`

### Step 2: Configure Build Settings

1. **Build Pack**: Select **Dockerfile**
2. **Base Directory**: Leave as `/` (root)
3. **Dockerfile Path**: `Dockerfile`
4. **Port**: `8501` (Streamlit default)

### Step 3: Set Environment Variables

Navigate to **Environment Variables** tab and add the following:

#### Required Variables

| Variable Name | Example Value | Description |
|--------------|---------------|-------------|
| `POSTGRES_PASSWORD` | `your_secure_password_here` | PostgreSQL database password |
| `SESSION_SECRET` | `your_random_secret_key` | Session encryption key (generate random string) |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | Your OpenRouter API key |
| `ADMIN_USERNAME` | `admin` | Login username (single-user mode) |
| `ADMIN_EMAIL` | `admin@trading.local` | Admin email address |
| `ADMIN_PASSWORD` | `your_secure_password` | Login password (change from default!) |

#### Optional Variables

| Variable Name | Default Value | Description |
|--------------|---------------|-------------|
| `POSTGRES_USER` | `trading` | Database username |
| `POSTGRES_DB` | `trading_db` | Database name |
| `FINNHUB_API_KEY` | _(empty)_ | Finnhub API key for market sentiment |
| `OPENROUTER_MODEL` | `anthropic/claude-3.5-sonnet` | AI model to use |
| `IBKR_HOST` | `127.0.0.1` | IBKR connection host |
| `IBKR_PAPER_PORT` | `7497` | TWS Paper trading port |
| `IBKR_LIVE_PORT` | `7496` | TWS Live trading port |
| `IBKR_GATEWAY_PORT` | `4002` | IB Gateway port |
| `IBKR_CLIENT_ID` | `1` | IBKR API client ID |

**How to set:**
1. Click "Add Environment Variable"
2. Enter Name and Value
3. Click "Update" to save each one
4. Mark `POSTGRES_PASSWORD`, `SESSION_SECRET`, `OPENROUTER_API_KEY`, and `ADMIN_PASSWORD` as **Secret** (eye icon)

### Step 4: Configure Docker Compose (Optional - Full Stack)

If deploying with PostgreSQL included:

1. **Build Pack**: Select **Docker Compose**
2. **Compose File**: `docker-compose.yml`
3. Set the same environment variables as above
4. Coolify will manage both app and database containers

### Step 5: Domain Configuration

1. **Add Domain** in Coolify
2. Enter your domain or use Coolify's provided domain
3. **SSL**: Coolify auto-generates Let's Encrypt certificates
4. **Port Mapping**: No need to expose ports manually (Coolify's Traefik handles routing)

### Step 6: Deploy

1. Click **Deploy** button
2. Monitor build logs in real-time
3. Wait for health check to pass (green status)
4. Access your app at the configured domain

---

## Generating Secure Secrets

Use these commands to generate secure random secrets:

```bash
# For SESSION_SECRET (32-character random string)
openssl rand -hex 32

# Or using Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Post-Deployment Configuration

### 1. Single-User Login
**This app operates in single-user mode.** Your admin credentials are set via environment variables.

- Navigate to your deployed app
- Login with the credentials you set:
  - Username: Value of `ADMIN_USERNAME` (default: `admin`)
  - Password: Value of `ADMIN_PASSWORD` (⚠️ **Change from default!**)
- The admin user is automatically created on first startup
- No signup page - credentials are managed via environment variables only

### 2. IBKR Connection Setup

**Important:** To use trading features, you need TWS/IB Gateway running:

- **Local Development**: IB Gateway on your machine
- **Production**: Consider running TWS/Gateway on a VPS with network access to your Coolify server

**Network Configuration:**
- Update `IBKR_HOST` environment variable to point to your TWS/Gateway instance
- Ensure firewall rules allow connection from Coolify server to IBKR ports

### 3. Database Migrations

**The app now uses an automatic SQL-based migration system** that safely handles schema updates on every redeployment.

#### How It Works

On every application startup:
1. **Migrations run FIRST** - Creates/updates all database tables
2. **Admin user created** - Using credentials from environment variables
3. **Orphan repair** - Assigns any legacy trades to admin user
4. **App starts** - Ready to use

#### Migration System Features

✅ **Automatic on Every Deploy** - No manual intervention needed  
✅ **Data Preservation** - Never loses existing data during schema updates  
✅ **Idempotent** - Safe to run multiple times  
✅ **Tracked** - `schema_migrations` table tracks applied migrations  
✅ **Transactional** - Rolls back on any error  

#### Production Database Upgrade

When redeploying to Coolify with schema changes:

1. **Push to GitHub** - Your code changes trigger Coolify redeploy
2. **Auto-migration** - App runs migrations on startup:
   - Backs up existing data (e.g., trades table)
   - Recreates tables with correct foreign key constraints
   - Restores all data
   - Assigns orphaned records to admin user
3. **Zero downtime** - Users can login immediately after deployment
4. **Data intact** - All historical trades preserved and queryable

#### Broken Production Database Fix

If your production database has schema errors (e.g., trades created before users):

- **Migration 001** automatically fixes it:
  - Backs up all trade data
  - Drops broken tables
  - Recreates with proper foreign key constraints
  - Restores all data
  - Assigns orphaned trades to admin
  - Adds indexes for performance

**No manual intervention required!** Just redeploy and the migration handles everything.

#### Adding New Migrations

For future schema changes:

1. Create new SQL file: `migrations/002_your_change.sql`
2. Write idempotent SQL (use `IF NOT EXISTS`, `DO $$ ... END $$;`)
3. Push to GitHub
4. Coolify redeploys and applies the new migration automatically

Example migration template:
```sql
-- Migration: 002_add_new_feature.sql
-- Description: Add new feature table

CREATE TABLE IF NOT EXISTS feature_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feature_user_id ON feature_data(user_id);
```

#### Monitoring Migrations

Check application logs during deployment:
```
INFO:migrations_manager:Applied migrations: 1
INFO:migrations_manager:✅ Database schema is up to date
INFO:__main__:Admin user created successfully
INFO:__main__:Assigned 0 orphaned trades to admin user
```

#### Database Schema

Current tables after migration 001:
- **users** - Admin account and authentication
- **user_settings** - User preferences and configuration
- **trades** - Trade history with FK to users
- **alerts** - Price alerts and notifications
- **schema_migrations** - Migration tracking

All foreign key constraints are properly enforced for data integrity.

---

## Troubleshooting

### "No Available Server" Error
- Check that health check is passing: `curl https://yourdomain.com/_stcore/health`
- Verify port 8501 is exposed in Dockerfile
- Check container logs in Coolify

### Environment Variables Not Working
- Ensure all required variables are set with correct values
- Click "Update" button after entering each variable
- Redeploy after changing environment variables

### Database Connection Failed
- Verify `DATABASE_URL` is correctly formatted
- Check PostgreSQL container is running and healthy
- Ensure `POSTGRES_PASSWORD` matches in all places

### IBKR Connection Issues
- Verify TWS/IB Gateway is running and accessible
- Check `IBKR_HOST` points to correct IP/hostname
- Ensure firewall allows connections on IBKR ports
- Verify API is enabled in TWS/Gateway settings

---

## Updating Your Deployment

### Push Updates to GitHub

```bash
git add .
git commit -m "Description of changes"
git push origin main
```

### Trigger Redeploy in Coolify

- Coolify auto-deploys on git push (if webhook configured)
- Or manually click "Deploy" button in Coolify UI

---

## Environment-Specific Notes

### Development (Replit)
- Runs on port 5000
- Uses Replit's PostgreSQL database
- Environment variables in `.env` file

### Production (Coolify)
- Runs on port 8501
- Uses PostgreSQL container (docker-compose) or external DB
- Environment variables in Coolify UI
- SSL/TLS enabled via Traefik

---

## Security Best Practices

1. **Never commit `.env` file** - It contains secrets
2. **Use strong passwords** for `POSTGRES_PASSWORD` and `SESSION_SECRET`
3. **Mark sensitive variables as Secret** in Coolify UI (hides from logs)
4. **Enable SSL/TLS** for your domain (Coolify does this automatically)
5. **Regular updates** - Keep dependencies up to date
6. **Backup database** - Use Coolify's backup features for PostgreSQL

---

## Support & Resources

- **Coolify Docs**: https://coolify.io/docs
- **Streamlit Docker Guide**: https://docs.streamlit.io/deploy/tutorials/docker
- **Interactive Brokers API**: https://www.interactivebrokers.com/en/trading/ib-api.php
- **GitHub Repository**: https://github.com/megadoom99/trading

---

## Quick Reference Commands

```bash
# Check if app is healthy
curl https://yourdomain.com/_stcore/health

# View Docker logs locally
docker-compose logs -f app

# Rebuild and restart locally
docker-compose up --build -d

# Stop all containers
docker-compose down

# Remove volumes (careful - deletes database!)
docker-compose down -v
```

---

## Architecture Overview

```
GitHub Repo (megadoom99/trading)
    ↓ (git push)
Coolify Server
    ├── Traefik Proxy (SSL/TLS, routing)
    ├── App Container (Streamlit on port 8501)
    └── PostgreSQL Container (port 5432)
```

External dependencies:
- OpenRouter API (AI models)
- Finnhub API (market data - optional)
- IB Gateway/TWS (trading execution)

---

**Ready to Deploy!** Follow the steps above and your trading app will be live on Coolify. 🚀
