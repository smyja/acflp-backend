# Comprehensive Production Deployment Guide

## 🏗️ Staging Environment Setup with CapRover

### Why Staging Matters
Staging environments are crucial for:
- Testing migrations with real-like data
- Validating performance under load
- Catching integration issues before production
- Safe rollback testing

### Setting Up Staging on CapRover

#### 1. Create Staging Subdomain
```bash
# In CapRover dashboard:
# 1. Create new app: "acflp-staging"
# 2. Set domain: staging.yourdomain.com
# 3. Enable HTTPS
```

#### 2. Database Strategy for Staging

**Production-Safe Database Sync (Recommended)**
```bash
#!/usr/bin/env bash
# weekly_staging_sync.sh
set -euo pipefail

: "${STAGING_SAFETY_LOCK:=disabled}"
if [ "$STAGING_SAFETY_LOCK" != "enabled" ]; then
  echo "Refusing to run without STAGING_SAFETY_LOCK=enabled"
  exit 1
fi

# Connection details
export PGPASSWORD_PROD="${PGPASSWORD_PROD:?set me}"
export PGPASSWORD_STAGING="${PGPASSWORD_STAGING:?set me}"
PROD_URL="host=prod_db_host user=postgres dbname=acflp_prod"
STAGING_URL="host=staging_db_host user=postgres dbname=acflp_staging"

# 1. Dump production in custom format
DUMP_FILE="/tmp/prod_backup_$(date +%Y%m%d%H%M%S).dump"
pg_dump -Fc --no-owner --no-privileges -Z9 -d "postgresql://${PROD_URL// /?}" > "$DUMP_FILE"

# 2. Restore into staging and drop existing objects
pg_restore --clean --if-exists --no-owner --no-privileges \
  -d "postgresql://${STAGING_URL// /?}" "$DUMP_FILE"

# 3. Anonymize sensitive data
psql "postgresql://${STAGING_URL// /?}" <<'SQL'
BEGIN;

-- Make emails undeliverable
UPDATE "user"
SET email = 'staging+' || id || '@example.invalid';

-- Disable all passwords
UPDATE "user"
SET hashed_password = '$2b$12$000000000000000000000uP2Qxj9Zb8qQY0RhfM3c0wL3tYtVZQyG'; -- clearly unusable

-- Nuke tokens and secrets
UPDATE api_tokens SET token = md5(random()::text) WHERE token IS NOT NULL;
UPDATE oauth_accounts SET access_token = NULL, refresh_token = NULL, provider_user_id = 'staging-' || provider_user_id;

-- Scrub PII
UPDATE profile
SET full_name = 'User ' || id,
    phone = NULL,
    address = NULL;

COMMIT;
SQL

echo "Sync complete and anonymized."
```

**⚠️ WARNING: Do Not Use Shared Database**

> **Do not use a shared database with a `staging` schema.** You will lose indexes and constraints with `CREATE TABLE AS`, sequences will drift, and application credentials can escape their lane. Use a separate database instance for staging.

#### 3. CapRover Staging Deployment

**captain-definition for staging**
```json
{
  "schemaVersion": 2,
  "dockerfilePath": "./Dockerfile",
  "env": {
    "ENVIRONMENT": "staging",
    "DATABASE_URL": "$$cap_staging_db_url",
    "EMAIL_SINK": "blackhole",
    "STAGING_SAFETY_LOCK": "enabled",
    "SMTP_HOST": "mailhog",
    "SMTP_PORT": "1025",
    "PAYMENT_PROVIDER_MODE": "test",
    "DISABLE_OUTBOUND_WEBHOOKS": "true"
  },
  "containerHttpPort": "8000"
}
```

**Add healthcheck to Dockerfile:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/health || exit 1
```

**Staging Safety Environment Variables**
```bash
# Staging environment variables
ENVIRONMENT=staging
STAGING_SAFETY_LOCK=enabled

# Email blackhole
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
EMAIL_SINK=blackhole  # your app should branch on this and never send externally

# Payments and webhooks
PAYMENT_PROVIDER_MODE=test
DISABLE_OUTBOUND_WEBHOOKS=true
```

## 🚩 Feature Flags: Open Source Solutions

### 1. **Unleash** (Recommended for Self-Hosted)

**Why Unleash:**
- Open source and self-hostable
- Great UI for non-technical users
- Gradual rollouts and A/B testing
- Client SDKs for Python/FastAPI

**CapRover One-Click Unleash Setup:**
```json
{
  "schemaVersion": 2,
  "dockerCompose": {
    "version": "3.8",
    "services": {
      "$$cap_appname": {
        "image": "unleashorg/unleash-server:latest",
        "ports": ["3000:4242"],
        "environment": {
          "DATABASE_URL": "$$cap_unleash_db_url",
          "DATABASE_SSL": "false",
          "INIT_ADMIN_API_TOKENS": "$$cap_unleash_admin_token"
        },
        "volumes": [
          "unleash-data:/var/lib/unleash"
        ],
        "healthcheck": {
          "test": ["CMD", "wget", "-qO-", "http://localhost:4242/health"],
          "interval": "30s",
          "timeout": "5s",
          "retries": 5
        }
      }
    },
    "volumes": { "unleash-data": {} }
  }
}
```

**Production-Safe FastAPI Integration:**
```python
# requirements.txt
UnleashClient==5.11.0

# src/app/core/feature_flags.py
from UnleashClient import UnleashClient
import os

UNLEASH_URL = os.getenv("UNLEASH_URL", "")
UNLEASH_TOKEN = os.getenv("UNLEASH_TOKEN", "")

client = None
if UNLEASH_URL and UNLEASH_TOKEN:
    client = UnleashClient(
        url=UNLEASH_URL,
        app_name="acflp-backend",
        custom_headers={"Authorization": UNLEASH_TOKEN}
    )
    client.initialize_client()

def is_feature_enabled(name: str, user_id: str | None = None, default: bool = False) -> bool:
    """Feature flag check with fallback when Unleash is unavailable"""
    if client is None:
        return default
    ctx = {"userId": user_id} if user_id else {}
    return client.is_enabled(name, context=ctx, default_value=default)

# Usage in API
if is_feature_enabled("spoken_languages", str(current_user.id), default=False):
    # New spoken_languages logic
else:
    # Old logic
```

### 2. **Flagsmith** (Alternative)

**Setup:**
```bash
# Self-hosted option
docker run -p 8000:8000 flagsmith/flagsmith:latest

# Or use their cloud service (free tier available)
```

**Python Integration:**
```python
from flagsmith import Flagsmith

flagsmith = Flagsmith(
    environment_key="your_environment_key",
    api_url="https://flagsmith.yourdomain.com/api/v1/"
)

def get_feature_flag(flag_name: str, user_id: str = None):
    if user_id:
        identity = flagsmith.get_identity_flags(user_id)
        return identity.is_feature_enabled(flag_name)
    else:
        flags = flagsmith.get_environment_flags()
        return flags.is_feature_enabled(flag_name)
```

### 3. **Simple Environment-Based Flags** (Minimal Approach)

```python
# src/app/core/feature_flags.py
import os, hashlib
from typing import Dict, Any

def stable_percent(user_id: str, salt: str) -> int:
    """Stable percentage calculation using cryptographic hash"""
    h = hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100

class SimpleFeatureFlags:
    def __init__(self):
        self.flags = {
            "spoken_languages": os.getenv("FEATURE_SPOKEN_LANGUAGES", "false").lower() == "true",
            "new_task_assignment": os.getenv("FEATURE_NEW_TASK_ASSIGNMENT", "false").lower() == "true",
            "admin_analytics": os.getenv("FEATURE_ADMIN_ANALYTICS", "false").lower() == "true",
        }
    
    def is_enabled(self, flag_name: str, user_context: Dict[str, Any] | None = None) -> bool:
        enabled = self.flags.get(flag_name, False)
        if not enabled:
            return False
        
        if user_context and "user_id" in user_context:
            rollout = int(os.getenv(f"ROLLOUT_{flag_name.upper()}", "100"))
            pct = stable_percent(str(user_context["user_id"]), flag_name)
            return pct < rollout
        
        return True

feature_flags = SimpleFeatureFlags()

# Usage
if feature_flags.is_enabled("spoken_languages", {"user_id": current_user.id}):
    # New logic
```

## 🏢 How FAANG Companies Handle This

### Google's Approach
1. **Staged Rollouts**: 1% → 5% → 25% → 50% → 100%
2. **Canary Deployments**: Deploy to single datacenter first
3. **Feature Flags**: Internal system called "Gflags"
4. **Automated Rollbacks**: Monitoring triggers automatic rollback
5. **Shadow Traffic**: Route copy of production traffic to new code

### Facebook/Meta's Strategy
1. **Gatekeeper**: Their feature flag system
2. **1% Rule**: Always test on 1% of users first
3. **Gradual Rollouts**: Increase percentage daily
4. **Quick Rollbacks**: Can disable features in seconds
5. **A/B Testing**: Built into feature flag system

### Netflix's Method
1. **Spinnaker**: Open-source deployment platform
2. **Chaos Engineering**: Intentionally break things to test resilience
3. **Blue-Green Deployments**: Maintain two identical environments
4. **Automated Canary Analysis**: AI-driven rollout decisions

### Amazon's Practices
1. **Cell-Based Architecture**: Isolate failures to small user groups
2. **One-Way Doors**: Irreversible changes get extra scrutiny
3. **Deployment Pipelines**: Automated testing at each stage
4. **Operational Readiness Reviews**: Manual approval for major changes

## 🛠️ Practical Implementation for Your Setup

### Phase 1: Basic Staging Setup

**1. Create Staging Environment**
```bash
# In CapRover:
# 1. Clone production app as "acflp-staging"
# 2. Set staging.yourdomain.com domain
# 3. Use separate database
```

**2. Environment Variables**
```bash
# Production
ENVIRONMENT=production
USE_SPOKEN_LANGUAGES=false
ROLLOUT_SPOKEN_LANGUAGES=0

# Staging
ENVIRONMENT=staging
USE_SPOKEN_LANGUAGES=true
ROLLOUT_SPOKEN_LANGUAGES=100
```

### Phase 2: Feature Flag Implementation

**1. Choose Your Tool**
- **Small team**: Simple environment flags
- **Growing team**: Unleash (self-hosted)
- **Enterprise**: Flagsmith or LaunchDarkly

**2. Implementation Pattern**
```python
# src/app/core/config.py
class Settings(BaseSettings):
    # ... existing settings
    
    # Feature flags
    feature_spoken_languages: bool = False
    rollout_spoken_languages: int = 0
    
    # Unleash integration (optional)
    unleash_url: str = ""
    unleash_token: str = ""

settings = Settings()

# src/app/api/v1/users.py
from app.core.feature_flags import feature_flags

@router.patch("/me/languages")
async def update_my_languages(...):
    if feature_flags.is_enabled("spoken_languages", {"user_id": current_user.id}):
        # New implementation
        current_user.spoken_languages = request.spoken_languages
    else:
        # Old implementation (backward compatibility)
        # Handle old source_languages/target_languages format
    
    await db.commit()
    return current_user
```

### Phase 3: Deployment Pipeline

**1. CI/CD with GitHub Actions**
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.test.yml up --abort-on-container-exit

  deploy-staging:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: >
          npx caprover deploy
          --caproverUrl ${{ secrets.CAPROVER_URL }}
          --appToken ${{ secrets.STAGING_APP_TOKEN }}
          --appName acflp-staging

  deploy-prod-canary:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://api.yourdomain.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy canary image
        run: >
          npx caprover deploy
          --caproverUrl ${{ secrets.CAPROVER_URL }}
          --appToken ${{ secrets.PROD_APP_TOKEN }}
          --appName acflp-backend-canary

  promote-prod:
    needs: deploy-prod-canary
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Promote canary to main service
        run: |
          # Flip traffic by updating main app to the tested tag
          npx caprover deploy \
            --caproverUrl ${{ secrets.CAPROVER_URL }} \
            --appToken ${{ secrets.PROD_APP_TOKEN }} \
            --appName acflp-backend
```

**2. Monitoring and Alerts**
```python
# src/app/core/monitoring.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
import logging

app = FastAPI()

# Metrics (avoid PII in labels)
feature_flag_usage = Counter(
    "feature_flag_usage_total",
    "Feature flag usage",
    ["flag_name", "enabled"]
)

api_latency = Histogram(
    "api_request_duration_seconds",
    "API latency"
)

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

def track_feature_usage(flag_name: str, enabled: bool):
    feature_flag_usage.labels(flag_name=flag_name, enabled=str(enabled)).inc()
    logging.info(f"Feature flag {flag_name} used: {enabled}")

# Usage in API
if feature_flags.is_enabled("spoken_languages", {"user_id": current_user.id}):
    track_feature_usage("spoken_languages", True)
    # New logic
else:
    track_feature_usage("spoken_languages", False)
    # Old logic
```

## 📋 Complete Deployment Checklist

### Pre-Deployment
- [ ] Staging environment set up and tested
- [ ] Database migration tested on staging
- [ ] Feature flags configured
- [ ] Monitoring and alerts configured
- [ ] Rollback plan documented
- [ ] Team notified of deployment window
- [ ] Staging safety locks verified (no outbound email/payments)
- [ ] Database backup completed
- [ ] Integration tests passing on staging

### Deployment Day
- [ ] Deploy to staging first
- [ ] Run integration tests on staging
- [ ] Deploy to production canary with feature flags OFF
- [ ] Verify application health
- [ ] Gradually enable feature flags (1% → 10% → 50% → 100%)
- [ ] Monitor metrics and error rates
- [ ] Verify no outbound communications from staging

### Post-Deployment
- [ ] Monitor for 24 hours
- [ ] Collect user feedback
- [ ] Analyze performance metrics
- [ ] Plan next iteration
- [ ] Document lessons learned

## 🔧 Tools and Resources

### Monitoring
- **Sentry**: Error tracking and performance monitoring
- **Prometheus + Grafana**: Metrics and dashboards
- **Uptime Robot**: Simple uptime monitoring

### Feature Flags
- **Unleash**: Self-hosted, open source
- **Flagsmith**: Cloud or self-hosted
- **LaunchDarkly**: Enterprise solution
- **PostHog**: Analytics + feature flags

### Deployment
- **CapRover**: Your current platform
- **GitHub Actions**: CI/CD
- **Docker**: Containerization
- **Watchtower**: Automatic container updates

### Safety Tools
- **MailHog**: Email testing/blackhole for staging
- **ngrok**: Secure tunneling for webhook testing
- **Testcontainers**: Integration testing with real databases

## 🚨 Production Safety Checklist

### Database Safety
- [ ] Use separate database instances for staging/prod
- [ ] Never share schemas between environments
- [ ] Always use custom format dumps (`pg_dump -Fc`)
- [ ] Anonymize all PII in staging data
- [ ] Set unusable passwords for staging users
- [ ] Create single test user with known credentials

### Communication Safety
- [ ] Route staging emails to blackhole (MailHog)
- [ ] Disable outbound webhooks in staging
- [ ] Use test mode for payment providers
- [ ] Block external API calls in staging

### Feature Flag Safety
- [ ] Use cryptographic hashing for stable rollouts
- [ ] Always have fallback when feature flag service is down
- [ ] Monitor feature flag usage metrics
- [ ] Document rollback procedures for each flag

### Deployment Safety
- [ ] Require manual approval for production deployments
- [ ] Use canary deployments before full rollout
- [ ] Monitor error rates during rollouts
- [ ] Have one-command rollback ready
- [ ] Test rollback procedures regularly

This approach gives you enterprise-grade deployment practices while working within your VPS + CapRover constraints!
