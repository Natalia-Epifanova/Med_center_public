WEEKLY POSTGRES BACKUP SET

Files:
1. backup_db.ps1
   Main PowerShell script for PostgreSQL backup.

2. backup_db.bat
   Wrapper for convenient launch from Windows Task Scheduler.

Recommended production values:
- ProjectDir: C:\Users\РевмаМед10\PycharmProjects\Medical_center
- BackupDir: C:\MedCenterBackups\Postgres
- KeepDays: 60

What the script does:
- Reads DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT from .env
- Runs pg_dump in custom format
- Creates a file like:
  medcenter_db_2026-04-04_23-30.dump
- Deletes old backups older than KeepDays

Important safety notes:
- Do not store backups inside the project folder
- Do not store backups inside media or any nginx-served directory
- Restrict access to the backup folder to administrators only
- These backups contain sensitive medical data

Manual test command:
backup_db.bat

If pg_dump is not found automatically:
- Edit backup_db.ps1
- Pass the correct PostgreSQL bin path through parameter -PgDumpPath

Tomorrow during setup in Task Scheduler:
- Run backup_db.bat once a week at night
- Use a user account that has access to:
  1. the project folder
  2. the .env file
  3. PostgreSQL
  4. the backup destination folder
