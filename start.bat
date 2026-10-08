@echo off
REM Double-click to start Axon (backend + website). Close this window or press Ctrl+C to stop.
cd /d "%~dp0"
start "" http://localhost:5173
node frontend\scripts\dev.mjs
