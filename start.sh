#!/bin/bash
set -e

echo "🚀 Starting AI Mapping Copilot..."

# Start backend
cd "$(dirname "$0")/backend"
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
echo $! > .server.pid
echo "✅ Backend started on http://localhost:8000"

# Start frontend
cd "$(dirname "$0")/frontend"
nohup npm run dev > frontend.log 2>&1 &
echo $! > .frontend.pid
echo "✅ Frontend started on http://localhost:5173"

echo ""
echo "📖 Open http://localhost:5173 in your browser"
echo "🛑 To stop: kill \$(cat backend/.server.pid) \$(cat frontend/.frontend.pid)"
