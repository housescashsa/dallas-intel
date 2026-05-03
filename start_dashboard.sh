#!/bin/bash
# Start API + dashboard in two terminal windows
osascript <<APPLESCRIPT
tell application "Terminal"
    do script "cd ~/Code/dallas-intel && source .venv/bin/activate && uvicorn dallas_intel.api:app --port 8000"
    do script "cd ~/Code/dallas-intel/dashboard && npm run dev"
end tell
APPLESCRIPT

sleep 4
open http://localhost:5173
