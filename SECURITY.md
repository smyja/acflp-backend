# Security Guidelines

## Overview

This document outlines the security measures implemented in the ACFLP Backend API and provides guidelines for maintaining security in production environments.

## Security Fixes Applied

### 1. Hardcoded Password Removal

**Issue**: Configuration files contained hardcoded default passwords that could be exploited.

**Fix**: 
- Removed hardcoded default passwords from `src/app/core/config.py`
- Updated `.env` and `.env.example` files with secure placeholder values
- Added clear comments indicating that values must be changed in production

**Files Modified**:
- `src/app/core/config.py`: Removed default passwords for MySQL, PostgreSQL, and Admin accounts
- `src/.env`: Updated with secure placeholder values
- `src/.env.example`: Updated with descriptive placeholder values

### 2. Environment Variable Security

**Best Practices Implemented**:
- All sensitive configuration values are loaded from environment variables
- No hardcoded secrets in source code
- Clear documentation for required environment variables

## Production Security Checklist

### Required Actions Before Deployment

1. **Generate Strong Secrets**:
   ```bash
   # Generate a strong SECRET_KEY (minimum 32 characters)
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Set Secure Passwords**:
   - `POSTGRES_PASSWORD`: Use a strong database password (minimum 12 characters)
   - `ADMIN_PASSWORD`: Use a strong admin password (minimum 8 characters with mixed case, numbers, symbols)

3. **Environment Variables**:
   - Ensure all environment variables are set in your production environment
   - Never commit `.env` files with real credentials to version control

4. **Database Security**:
   - Use SSL/TLS for database connections in production
   - Restrict database access to application servers only
   - Regular database backups with encryption

5. **API Security**:
   - Enable HTTPS in production
   - Configure CORS properly for your frontend domains
   - Set up rate limiting
   - Regular security audits

## Security Features

### Authentication & Authorization
- JWT-based authentication with configurable expiration
- Password hashing using bcrypt
- OAuth integration (Google SSO)
- Role-based access control

### Data Protection
- SQL injection prevention through SQLAlchemy ORM
- Input validation using Pydantic schemas
- Secure password storage (hashed, never plain text)

### Infrastructure Security
- Non-root user in Docker containers
- Security scanning with Bandit
- Dependency vulnerability scanning
- Multi-stage Docker builds

## Security Monitoring

### CI/CD Security Checks
- Bandit security linting
- Safety vulnerability scanning
- Automated security testing in GitHub Actions

### Recommended Monitoring
- Log authentication failures
- Monitor for unusual API access patterns
- Set up alerts for failed security scans
- Regular dependency updates

## Reporting Security Issues

If you discover a security vulnerability, please:
1. **DO NOT** create a public GitHub issue
2. Email the security team at: maro@acflp.org
3. Include detailed information about the vulnerability
4. Allow time for the issue to be addressed before public disclosure

## Security Resources

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Python Security Best Practices](https://python.org/dev/security/)

---

**Last Updated**: January 2025
**Version**: 1.0.0