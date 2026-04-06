#!/bin/bash
# AI Portal V2 Development Startup Script
# This script starts the backend with Fake SSO mode enabled

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 AI Portal V2 - Development Mode with Fake SSO"
echo "================================================"
echo ""

# Check if backend dependencies are installed
cd "$PROJECT_ROOT/backend"
echo "📦 Checking Python dependencies..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "❌ Python dependencies not installed. Installing..."
    pip install -r requirements.txt
}

# Verify configuration
echo "🔧 Verifying configuration..."
if [ -f ".env" ]; then
    echo "✓ Backend .env found"
else
    echo "⚠️  Backend .env not found, creating from example..."
    cp ../.env.example .env
fi

cd "$PROJECT_ROOT/frontend"
if [ -f ".env" ]; then
    echo "✓ Frontend .env found"
else
    echo "⚠️  Frontend .env not found, creating..."
    echo "VITE_API_BASE_URL=http://localhost:8000" > .env
    echo "VITE_APP_NAME=AI Portal" >> .env
fi

# Check node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

echo ""
echo "🔐 Fake SSO Mode: ENABLED"
echo "   - Any authorization code will be accepted"
echo "   - Default user: E10001 (测试用户)"
echo "   - Roles: employee, admin"
echo ""
echo "📝 Access Information:"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API Docs: http://localhost:8000/docs"
echo ""

# Start backend in background
cd "$PROJECT_ROOT/backend"
echo "🟢 Starting backend server..."
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ Backend is ready"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
done

echo ""

# Start frontend
cd "$PROJECT_ROOT/frontend"
echo "🟢 Starting frontend dev server..."
echo ""
npm run dev

# Cleanup on exit
echo ""
echo "🛑 Shutting down..."
kill $BACKEND_PID 2>/dev/null || true
