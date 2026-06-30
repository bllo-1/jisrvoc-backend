#!/bin/bash
set -e

echo "🚀 Phase 3 Deployment Script"
echo "=============================="
echo ""

# Check if Docker Compose is running
if ! docker compose ps | grep -q "Up"; then
    echo "⚠️  Docker Compose is not running. Starting..."
    docker compose up -d
    echo "✅ Containers started"
    sleep 5
else
    echo "✅ Docker Compose is already running"
fi

echo ""
echo "Step 1: Running Alembic migrations..."
echo "--------------------------------------"
docker compose exec -T api alembic upgrade head
echo "✅ Migrations completed"

echo ""
echo "Step 2: Activating Phase 3 routes..."
echo "-------------------------------------"
if [ -f "app/api/router_phase3.py" ]; then
    # Backup existing router
    if [ -f "app/api/router.py" ]; then
        cp app/api/router.py app/api/router.py.backup
        echo "✅ Backed up existing router to router.py.backup"
    fi

    # Activate Phase 3
    cp app/api/router_phase3.py app/api/router.py
    echo "✅ Phase 3 routes activated"
else
    echo "⚠️  router_phase3.py not found, skipping route activation"
fi

echo ""
echo "Step 3: Restarting API server..."
echo "---------------------------------"
docker compose restart api
sleep 3
echo "✅ API server restarted"

echo ""
echo "Step 4: Verifying deployment..."
echo "--------------------------------"

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is responding"
        break
    fi
    sleep 1
done

echo ""
echo "Testing Phase 3 endpoints..."
echo ""

# Test overview metrics
echo "📊 Testing /api/v1/overview/metrics"
if curl -s http://localhost:8000/api/v1/overview/metrics | grep -q "total_items"; then
    echo "✅ Overview metrics working"
else
    echo "⚠️  Overview metrics may need data"
fi

# Test feedback endpoint
echo "📋 Testing /api/v1/feedback"
if curl -s "http://localhost:8000/api/v1/feedback?limit=5" | grep -q "items"; then
    echo "✅ Feedback endpoint working"
else
    echo "⚠️  Feedback endpoint may need data"
fi

echo ""
echo "=============================="
echo "🎉 Phase 3 Deployment Complete!"
echo "=============================="
echo ""
echo "Next steps:"
echo "1. Populate data: curl -X POST http://localhost:8000/api/v1/connectors/hubspot/sync"
echo "2. Run enrichment: curl -X POST http://localhost:8000/api/v1/enrichment/process"
echo "3. View API docs: http://localhost:8000/docs"
echo ""
echo "Test all Phase 3 features:"
echo "- Overview: curl http://localhost:8000/api/v1/overview/metrics"
echo "- Filters: curl 'http://localhost:8000/api/v1/feedback?area=payroll&urgency=high'"
echo "- Search: curl 'http://localhost:8000/api/v1/feedback?q=salary&limit=10'"
echo ""
