#!/bin/bash
cd "$(dirname "$0")"
python3 app.py &
PID=$!
sleep 3
echo "=== STATUS ==="
curl -s http://localhost:5001/api/status
echo ""
echo "=== SEARCH API ==="
curl -s "http://localhost:5001/api/search?q=test"
echo ""
echo "=== INTERVIEWS API ==="
curl -s http://localhost:5001/api/interviews
echo ""
kill $PID 2>/dev/null
