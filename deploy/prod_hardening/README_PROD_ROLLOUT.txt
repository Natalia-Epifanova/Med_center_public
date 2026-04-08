FILES IN THIS FOLDER ARE PREPARED TEMPLATES FOR TOMORROW'S PRODUCTION WINDOW.

What to copy to production:
1. deploy\prod_hardening\run_production.py
   Replace the production run_production.py with this file.

2. deploy\prod_hardening\nginx.conf
   Use this as the new nginx.conf, but first compare paths and server_name with production.

Important:
- This rollout DOES NOT enable HTTPS yet.
- Browser label "Not secure" will remain until HTTPS is configured.
- This rollout is meant to improve safety without breaking internal network access.

Before replacing files on production, back up:
- nginx.conf
- run_production.py
- start_all.py
- start_medcenter.bat
- config/settings.py
- .env

Recommended production order:
1. Backup old files.
2. Replace run_production.py.
3. Replace nginx.conf.
4. Validate nginx config: nginx.exe -t
5. Restart nginx.
6. Restart the Django application.
7. Verify from server and from another workstation.

Fast rollback:
1. Restore the backed-up nginx.conf and run_production.py.
2. Restart nginx.
3. Restart the old application launch flow.

Settings note:
- Your Django settings were already hardened in the test project.
- DO NOT enable SSL-only Django settings on production until HTTPS is actually configured.
