# Run this script from the project root: .\scripts\run_dev.ps1

Write-Host "Starting OmniRetail AI dev environment..."

if (-Not (Test-Path -Path .env)) {
    Write-Host ".env file not found. Please copy .env.example to .env and update values." -ForegroundColor Yellow
    exit 1
}

Write-Host "Loading environment variables from .env"
Get-Content .env | ForEach-Object {
    if ($_ -and -not $_.Trim().StartsWith('#')) {
        $parts = $_ -split '='
        if ($parts.Count -ge 2) {
            $key = $parts[0].Trim()
            $value = ($parts[1..($parts.Count - 1)] -join '=').Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value)
        }
    }
}

Write-Host "Running ETL loader..."
python scripts/load_csv_data.py

Write-Host "Starting FastAPI app at http://127.0.0.1:8000"
python -m uvicorn app.main:app --reload
