param(
    [string]$ProjectDir = "C:\Users\РевмаМед10\PycharmProjects\Medical_center",
    [string]$BackupDir = "C:\MedCenterBackups\Postgres",
    [int]$KeepDays = 60,
    [string]$PgDumpPath = ""
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Import-DotEnv {
    param([string]$EnvFile)

    if (-not (Test-Path -LiteralPath $EnvFile)) {
        throw "Файл .env не найден: $EnvFile"
    }

    Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            return
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Resolve-PgDumpPath {
    param([string]$ConfiguredPath)

    if ($ConfiguredPath -and (Test-Path -LiteralPath $ConfiguredPath)) {
        return $ConfiguredPath
    }

    $candidates = @(
        "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\13\bin\pg_dump.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "pg_dump.exe не найден. Укажите путь через параметр -PgDumpPath."
}

$envFile = Join-Path $ProjectDir ".env"
Import-DotEnv -EnvFile $envFile

$dbName = [System.Environment]::GetEnvironmentVariable("DATABASE_NAME", "Process")
$dbUser = [System.Environment]::GetEnvironmentVariable("DATABASE_USER", "Process")
$dbPassword = [System.Environment]::GetEnvironmentVariable("DATABASE_PASSWORD", "Process")
$dbHost = [System.Environment]::GetEnvironmentVariable("DATABASE_HOST", "Process")
$dbPort = [System.Environment]::GetEnvironmentVariable("DATABASE_PORT", "Process")

if (-not $dbName) { throw "DATABASE_NAME не задан в .env" }
if (-not $dbUser) { throw "DATABASE_USER не задан в .env" }
if (-not $dbPassword) { throw "DATABASE_PASSWORD не задан в .env" }
if (-not $dbHost) { $dbHost = "localhost" }
if (-not $dbPort) { $dbPort = "5432" }

$resolvedPgDump = Resolve-PgDumpPath -ConfiguredPath $PgDumpPath

if (-not (Test-Path -LiteralPath $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$backupFile = Join-Path $BackupDir ("medcenter_db_{0}.dump" -f $timestamp)

Write-Log "Начинаю резервное копирование базы '$dbName'"
Write-Log "Файл: $backupFile"

$env:PGPASSWORD = $dbPassword

try {
    & $resolvedPgDump `
        --host=$dbHost `
        --port=$dbPort `
        --username=$dbUser `
        --format=custom `
        --blobs `
        --verbose `
        --file=$backupFile `
        $dbName

    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump завершился с кодом $LASTEXITCODE"
    }

    Write-Log "Резервная копия успешно создана"

    $cutoffDate = (Get-Date).AddDays(-$KeepDays)
    Get-ChildItem -LiteralPath $BackupDir -Filter "medcenter_db_*.dump" -File |
        Where-Object { $_.LastWriteTime -lt $cutoffDate } |
        ForEach-Object {
            Write-Log "Удаляю старый бэкап: $($_.FullName)"
            Remove-Item -LiteralPath $_.FullName -Force
        }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
