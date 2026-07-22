# Offline Demo Recovery

The runtime uses no CDN, remote font, cloud, threat-intelligence, model-download, analytics, or external MITRE request. Browser traffic is limited to the selected localhost frontend, REST API, and WebSocket.

If startup fails, read `.aegistwin-demo/logs/launcher.log` and service error logs, run stop, then retry. For corrupt isolated state, use reset. This preserves source, developer databases, and tracked benchmark reports.

Prepare transfer media with `scripts\demo\create_demo_package.ps1`. Dependencies are excluded by default, so install them once while internet access is available. Label any retained completed database: “Backup demonstration evidence from a previously completed synthetic run.” The live application never automatically loads it.
