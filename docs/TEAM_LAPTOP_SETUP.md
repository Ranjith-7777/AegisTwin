# Team Laptop Setup

Install Python 3.11-3.14 and Node.js 20-24. Clone or extract AegisTwin, run `SETUP_AEGISTWIN_DEMO.bat`, then `START_AEGISTWIN_DEMO.bat`. Stop with `STOP_AEGISTWIN_DEMO.bat`; reset isolated data with `RESET_AEGISTWIN_DEMO.bat -Force`.

No FastAPI, Vite, or Alembic knowledge is required. A Windows Firewall prompt should be denied for public networks: the demo binds to loopback only. If ports 8000 or 5173 are occupied, do not kill the listener; use alternative `-BackendPort` and `-FrontendPort` values on the PowerShell launcher.

Use status to confirm connectivity. Logs are under `.aegistwin-demo/logs`. Never delete `backend/aegistwin.db`; reset targets only `.aegistwin-demo`.
