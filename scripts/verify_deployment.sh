#!/bin/bash
#
# Production Deployment Verification Script
# Runs post-deployment checks to ensure JisrVOC is healthy
#

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration (override with environment variables)
API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-10}"

echo "========================================"
echo "JisrVOC Production Deployment Verification"
echo "========================================"
echo ""
echo "API URL: $API_URL"
echo ""

# Counter for passed/failed checks
PASSED=0
FAILED=0

# Helper function to check HTTP endpoint
check_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}

    echo -n "Checking $name... "

    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url" 2>/dev/null || echo "000")

    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $response, expected $expected_status)"
        ((FAILED++))
        return 1
    fi
}

# Helper function to check JSON response
check_json_field() {
    local name=$1
    local url=$2
    local jq_filter=$3
    local expected=$4

    echo -n "Checking $name... "

    response=$(curl -s --max-time $TIMEOUT "$url" 2>/dev/null)
    actual=$(echo "$response" | jq -r "$jq_filter" 2>/dev/null || echo "ERROR")

    if [ "$actual" = "$expected" ]; then
        echo -e "${GREEN}✓ PASS${NC} ($actual)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (got: $actual, expected: $expected)"
        ((FAILED++))
        return 1
    fi
}

echo "=== Phase 1: Basic Health Checks ==="
check_endpoint "Health endpoint" "$API_URL/health" 200
check_endpoint "Readiness endpoint" "$API_URL/api/v1/readyz" 200
check_json_field "Database connectivity" "$API_URL/api/v1/readyz" '.checks.database' 'ok'
check_json_field "Redis connectivity" "$API_URL/api/v1/readyz" '.checks.redis' 'ok'
echo ""

echo "=== Phase 2: API Documentation ==="
check_endpoint "OpenAPI docs" "$API_URL/docs" 200
check_endpoint "OpenAPI JSON" "$API_URL/api/v1/openapi.json" 200
echo ""

echo "=== Phase 3: Core Endpoints ==="
check_endpoint "Overview metrics" "$API_URL/api/v1/overview/metrics" 200
check_endpoint "Feedback list" "$API_URL/api/v1/feedback?limit=10" 200
check_endpoint "Themes list" "$API_URL/api/v1/themes" 200
check_endpoint "Bets list" "$API_URL/api/v1/bets" 200
echo ""

echo "=== Phase 4: Database Checks ==="
if command -v psql &> /dev/null && [ -n "$DATABASE_URL" ]; then
    echo -n "Checking feedback_item table... "
    count=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM feedback_item;" 2>/dev/null | xargs)
    if [ -n "$count" ]; then
        echo -e "${GREEN}✓ PASS${NC} ($count rows)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC} (table not accessible)"
        ((FAILED++))
    fi

    echo -n "Checking Phase 5 enrichment columns... "
    cols=$(psql "$DATABASE_URL" -t -c "\d feedback_item" 2>/dev/null | grep -E "customer_mrr|customer_ltv|churn_risk_score" | wc -l | xargs)
    if [ "$cols" -ge 3 ]; then
        echo -e "${GREEN}✓ PASS${NC} (enrichment columns exist)"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠ WARN${NC} (enrichment columns not found - Phase 5 migration pending)"
    fi
else
    echo -e "${YELLOW}⚠ SKIP${NC} Database checks (psql not available or DATABASE_URL not set)"
fi
echo ""

echo "=== Phase 5: Celery Worker Checks ==="
if command -v celery &> /dev/null && [ -n "$REDIS_URL" ]; then
    echo -n "Checking Celery worker status... "
    celery_status=$(celery -A app.core.celery_app inspect active 2>/dev/null || echo "ERROR")
    if echo "$celery_status" | grep -q "Error"; then
        echo -e "${RED}✗ FAIL${NC} (worker not responding)"
        ((FAILED++))
    else
        echo -e "${GREEN}✓ PASS${NC} (worker active)"
        ((PASSED++))
    fi

    echo -n "Checking Celery queues... "
    queues=$(celery -A app.core.celery_app inspect active_queues 2>/dev/null | grep -o '"name":' | wc -l | xargs)
    if [ "$queues" -ge 5 ]; then
        echo -e "${GREEN}✓ PASS${NC} ($queues queues configured)"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠ WARN${NC} (expected 5 queues, found $queues)"
    fi
else
    echo -e "${YELLOW}⚠ SKIP${NC} Celery checks (celery not available or REDIS_URL not set)"
fi
echo ""

echo "=== Summary ==="
TOTAL=$((PASSED + FAILED))
echo "Total checks: $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Deployment is healthy.${NC}"
    exit 0
elif [ $FAILED -le 2 ]; then
    echo -e "${YELLOW}⚠ Some checks failed. Review and fix issues.${NC}"
    exit 1
else
    echo -e "${RED}✗ Multiple checks failed. Deployment may have issues.${NC}"
    exit 1
fi
