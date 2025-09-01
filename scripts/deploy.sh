#!/bin/bash

# Enterprise Deployment Script
# Automates deployment process with comprehensive checks and rollback capabilities

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/deploy-$(date +%Y%m%d-%H%M%S).log"
CONFIG_FILE="${PROJECT_ROOT}/.deploy.conf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="staging"
SKIP_TESTS=false
SKIP_SECURITY=false
FORCE_DEPLOY=false
ROLLBACK=false
VERBOSE=false
DRY_RUN=false

# Logging functions
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

# Help function
show_help() {
    cat << EOF
Enterprise Deployment Script

Usage: $0 [OPTIONS]

Options:
    -e, --environment ENV    Target environment (staging|production) [default: staging]
    -t, --skip-tests        Skip test execution
    -s, --skip-security     Skip security checks
    -f, --force             Force deployment even if checks fail
    -r, --rollback          Rollback to previous version
    -v, --verbose           Enable verbose output
    -d, --dry-run           Show what would be done without executing
    -h, --help              Show this help message

Examples:
    $0 --environment production
    $0 --environment staging --skip-tests
    $0 --rollback --environment production
    $0 --dry-run --environment production

Environment Variables:
    DOCKER_REGISTRY         Docker registry URL
    IMAGE_TAG              Docker image tag
    DEPLOY_KEY             Deployment key for authentication
    SLACK_WEBHOOK          Slack webhook for notifications

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -t|--skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            -s|--skip-security)
                SKIP_SECURITY=true
                shift
                ;;
            -f|--force)
                FORCE_DEPLOY=true
                shift
                ;;
            -r|--rollback)
                ROLLBACK=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
        log_info "Configuration loaded from $CONFIG_FILE"
    fi

    # Set defaults if not provided
    DOCKER_REGISTRY=${DOCKER_REGISTRY:-"ghcr.io"}
    IMAGE_TAG=${IMAGE_TAG:-"latest"}
    DEPLOY_TIMEOUT=${DEPLOY_TIMEOUT:-300}
    HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-60}
}

# Setup logging
setup_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    log_info "Deployment started for environment: $ENVIRONMENT"
    log_info "Log file: $LOG_FILE"
}

# Validate environment
validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"

    case $ENVIRONMENT in
        staging|production)
            log_success "Environment validation passed"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT. Must be 'staging' or 'production'"
            exit 1
            ;;
    esac
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."

    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        log_error "Not in project root directory"
        exit 1
    fi

    # Check Git status
    if [[ -n "$(git status --porcelain)" ]] && [[ "$FORCE_DEPLOY" != true ]]; then
        log_error "Working directory is not clean. Commit or stash changes first."
        exit 1
    fi

    # Check if on correct branch
    current_branch=$(git branch --show-current)
    if [[ "$ENVIRONMENT" == "production" ]] && [[ "$current_branch" != "main" ]] && [[ "$FORCE_DEPLOY" != true ]]; then
        log_error "Production deployments must be from 'main' branch. Current branch: $current_branch"
        exit 1
    fi

    # Check required tools
    for tool in docker docker-compose uv pytest; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool not found: $tool"
            exit 1
        fi
    done

    log_success "Pre-deployment checks passed"
}

# Run tests
run_tests() {
    if [[ "$SKIP_TESTS" == true ]]; then
        log_warning "Skipping tests as requested"
        return 0
    fi

    log_info "Running test suite..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would run: make ci-test"
        return 0
    fi

    if ! make ci-test; then
        if [[ "$FORCE_DEPLOY" == true ]]; then
            log_warning "Tests failed but continuing due to --force flag"
        else
            log_error "Tests failed. Use --force to deploy anyway or fix the issues."
            exit 1
        fi
    else
        log_success "All tests passed"
    fi
}

# Run security checks
run_security_checks() {
    if [[ "$SKIP_SECURITY" == true ]]; then
        log_warning "Skipping security checks as requested"
        return 0
    fi

    log_info "Running security checks..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would run: make ci-security"
        return 0
    fi

    if ! make ci-security; then
        if [[ "$FORCE_DEPLOY" == true ]]; then
            log_warning "Security checks failed but continuing due to --force flag"
        else
            log_error "Security checks failed. Use --force to deploy anyway or fix the issues."
            exit 1
        fi
    else
        log_success "Security checks passed"
    fi
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."

    local image_name="${DOCKER_REGISTRY}/acflp-backend:${IMAGE_TAG}"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would build: $image_name"
        return 0
    fi

    if ! docker build --target production -t "$image_name" .; then
        log_error "Docker build failed"
        exit 1
    fi

    log_success "Docker image built successfully: $image_name"
}

# Push Docker image
push_image() {
    log_info "Pushing Docker image to registry..."

    local image_name="${DOCKER_REGISTRY}/acflp-backend:${IMAGE_TAG}"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would push: $image_name"
        return 0
    fi

    if ! docker push "$image_name"; then
        log_error "Docker push failed"
        exit 1
    fi

    log_success "Docker image pushed successfully"
}

# Deploy to environment
deploy() {
    log_info "Deploying to $ENVIRONMENT environment..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would deploy to $ENVIRONMENT"
        return 0
    fi

    case $ENVIRONMENT in
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
    esac
}

# Deploy to staging
deploy_staging() {
    log_info "Deploying to staging environment..."

    # Update staging deployment
    if ! kubectl set image deployment/acflp-backend-staging acflp-backend="${DOCKER_REGISTRY}/acflp-backend:${IMAGE_TAG}" --namespace=staging; then
        log_error "Staging deployment failed"
        exit 1
    fi

    # Wait for rollout
    if ! kubectl rollout status deployment/acflp-backend-staging --namespace=staging --timeout="${DEPLOY_TIMEOUT}s"; then
        log_error "Staging rollout failed"
        exit 1
    fi

    log_success "Staging deployment completed"
}

# Deploy to production
deploy_production() {
    log_info "Deploying to production environment..."

    # Additional confirmation for production
    if [[ "$FORCE_DEPLOY" != true ]]; then
        read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Production deployment cancelled by user"
            exit 0
        fi
    fi

    # Blue-green deployment for production
    log_info "Starting blue-green deployment..."

    # Deploy to green environment first
    if ! kubectl set image deployment/acflp-backend-green acflp-backend="${DOCKER_REGISTRY}/acflp-backend:${IMAGE_TAG}" --namespace=production; then
        log_error "Green deployment failed"
        exit 1
    fi

    # Wait for green rollout
    if ! kubectl rollout status deployment/acflp-backend-green --namespace=production --timeout="${DEPLOY_TIMEOUT}s"; then
        log_error "Green rollout failed"
        exit 1
    fi

    # Health check on green environment
    if ! health_check "green"; then
        log_error "Health check failed on green environment"
        exit 1
    fi

    # Switch traffic to green
    if ! kubectl patch service acflp-backend-service -p '{"spec":{"selector":{"version":"green"}}}' --namespace=production; then
        log_error "Failed to switch traffic to green"
        exit 1
    fi

    log_success "Production deployment completed"
}

# Health check
health_check() {
    local version=${1:-"current"}
    log_info "Running health check for $version version..."

    local health_url
    case $ENVIRONMENT in
        staging)
            health_url="https://staging-api.acflp.com/api/v1/health"
            ;;
        production)
            if [[ "$version" == "green" ]]; then
                health_url="https://green-api.acflp.com/api/v1/health"
            else
                health_url="https://api.acflp.com/api/v1/health"
            fi
            ;;
    esac

    local attempts=0
    local max_attempts=$((HEALTH_CHECK_TIMEOUT / 5))

    while [[ $attempts -lt $max_attempts ]]; do
        if curl -f -s "$health_url" > /dev/null; then
            log_success "Health check passed for $version version"
            return 0
        fi

        attempts=$((attempts + 1))
        log_info "Health check attempt $attempts/$max_attempts failed, retrying in 5 seconds..."
        sleep 5
    done

    log_error "Health check failed after $max_attempts attempts"
    return 1
}

# Rollback deployment
rollback_deployment() {
    log_info "Rolling back deployment in $ENVIRONMENT environment..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would rollback deployment in $ENVIRONMENT"
        return 0
    fi

    case $ENVIRONMENT in
        staging)
            kubectl rollout undo deployment/acflp-backend-staging --namespace=staging
            kubectl rollout status deployment/acflp-backend-staging --namespace=staging
            ;;
        production)
            # Switch back to blue environment
            kubectl patch service acflp-backend-service -p '{"spec":{"selector":{"version":"blue"}}}' --namespace=production
            ;;
    esac

    log_success "Rollback completed"
}

# Send notification
send_notification() {
    local status=$1
    local message=$2

    if [[ -n "${SLACK_WEBHOOK:-}" ]]; then
        local color
        case $status in
            success) color="good" ;;
            warning) color="warning" ;;
            error) color="danger" ;;
            *) color="#439FE0" ;;
        esac

        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "Deployment Notification",
            "text": "$message",
            "fields": [
                {
                    "title": "Environment",
                    "value": "$ENVIRONMENT",
                    "short": true
                },
                {
                    "title": "Image Tag",
                    "value": "$IMAGE_TAG",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date)",
                    "short": false
                }
            ]
        }
    ]
}
EOF
        )

        curl -X POST -H 'Content-type: application/json' --data "$payload" "$SLACK_WEBHOOK" || true
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    # Add cleanup logic here
}

# Main deployment function
main() {
    parse_args "$@"
    load_config
    setup_logging

    # Set up trap for cleanup
    trap cleanup EXIT

    if [[ "$ROLLBACK" == true ]]; then
        rollback_deployment
        send_notification "success" "Rollback completed for $ENVIRONMENT environment"
        exit 0
    fi

    validate_environment
    pre_deployment_checks
    run_tests
    run_security_checks
    build_image
    push_image
    deploy
    health_check

    log_success "Deployment completed successfully!"
    send_notification "success" "Deployment completed successfully for $ENVIRONMENT environment"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
