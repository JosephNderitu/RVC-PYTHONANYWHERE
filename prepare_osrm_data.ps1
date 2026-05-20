# prepare_osrm_data.ps1
# Run from project root: .\prepare_osrm_data.ps1
# Downloads GA, TN, KY, AL, SC, NC road data and merges into southeast.osm.pbf

$ErrorActionPreference = "Stop"
$DataDir = Join-Path $PSScriptRoot "osrm_data"

Write-Host ""
Write-Host "RVC OSRM Data Preparation - Southeastern US" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
    Write-Host "Created osrm_data/ directory" -ForegroundColor Green
}

$BaseUrl = "https://download.geofabrik.de/north-america/us"

$StateNames = @("georgia", "tennessee", "kentucky", "alabama", "south-carolina", "north-carolina")
$StateLabels = @("Georgia", "Tennessee", "Kentucky", "Alabama", "South Carolina", "North Carolina")
$StateSizes  = @("~200MB", "~150MB", "~150MB", "~120MB", "~80MB", "~180MB")

Write-Host "Step 1 of 3 - Downloading state road network files" -ForegroundColor Yellow
Write-Host ""

for ($i = 0; $i -lt $StateNames.Count; $i++) {
    $sname  = $StateNames[$i]
    $slabel = $StateLabels[$i]
    $ssize  = $StateSizes[$i]
    $sfile  = $sname + "-latest.osm.pbf"
    $fpath  = Join-Path $DataDir $sfile
    $url    = $BaseUrl + "/" + $sfile

    if (Test-Path $fpath) {
        $mb = [math]::Round((Get-Item $fpath).Length / 1MB, 1)
        Write-Host ("  SKIP: " + $slabel + " already exists (" + $mb + " MB)") -ForegroundColor DarkGray
        continue
    }

    Write-Host ("  Downloading " + $slabel + " (" + $ssize + ")...") -ForegroundColor White
    Write-Host ("  URL: " + $url) -ForegroundColor DarkGray

    try {
        & curl.exe -L -o $fpath $url --progress-bar
        $mb = [math]::Round((Get-Item $fpath).Length / 1MB, 1)
        Write-Host ("  OK: " + $slabel + " downloaded (" + $mb + " MB)") -ForegroundColor Green
    } catch {
        Write-Host ("  ERROR: Failed to download " + $slabel + ": " + $_) -ForegroundColor Red
        Write-Host ("  Download manually from: " + $url) -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
}

Write-Host ""
Write-Host "Step 2 of 3 - Merging state files into southeast.osm.pbf" -ForegroundColor Yellow
Write-Host "  Using osmium-tool via Docker..." -ForegroundColor White
Write-Host ""

$OutFile = Join-Path $DataDir "southeast.osm.pbf"

if (Test-Path $OutFile) {
    Write-Host "  SKIP: southeast.osm.pbf already exists. Delete it to regenerate." -ForegroundColor DarkGray
} else {
    $InputArgs = @()
    for ($i = 0; $i -lt $StateNames.Count; $i++) {
        $InputArgs += "/data/" + $StateNames[$i] + "-latest.osm.pbf"
    }

    Write-Host ("  Merging " + $StateNames.Count + " files into southeast.osm.pbf") -ForegroundColor White
    Write-Host "  This takes 5-10 minutes. Please wait..." -ForegroundColor DarkGray
    Write-Host ""

    $DockerArgs = @("run", "--rm", "-v", ($DataDir + ":/data"), "mlocati/osmium-tool", "osmium", "merge", "--overwrite", "-o", "/data/southeast.osm.pbf") + $InputArgs

    & docker @DockerArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: osmium merge failed." -ForegroundColor Red
        Write-Host "Install osmium-tool locally and run:" -ForegroundColor Yellow
        $files = ""
        for ($i = 0; $i -lt $StateNames.Count; $i++) {
            $files += "osrm_data\" + $StateNames[$i] + "-latest.osm.pbf "
        }
        Write-Host ("  osmium merge " + $files + "-o osrm_data\southeast.osm.pbf") -ForegroundColor White
        exit 1
    }

    $mb = [math]::Round((Get-Item $OutFile).Length / 1MB, 0)
    Write-Host ""
    Write-Host ("  OK: southeast.osm.pbf created (" + $mb + " MB)") -ForegroundColor Green
}

Write-Host ""
$ans = Read-Host "Step 3 of 3 - Delete individual state PBFs to save disk space? (y/N)"

if ($ans -eq "y" -or $ans -eq "Y") {
    for ($i = 0; $i -lt $StateNames.Count; $i++) {
        $fpath = Join-Path $DataDir ($StateNames[$i] + "-latest.osm.pbf")
        if (Test-Path $fpath) {
            Remove-Item $fpath
            Write-Host ("  Deleted " + $StateNames[$i] + "-latest.osm.pbf") -ForegroundColor DarkGray
        }
    }
    Write-Host "  OK: State files cleaned up" -ForegroundColor Green
} else {
    Write-Host "  Keeping state files." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Done! Next steps:" -ForegroundColor Green
Write-Host "  1. Copy docker-compose-updated.yml to docker-compose.yml"
Write-Host "  2. docker compose down"
Write-Host "  3. docker compose up --build -d"
Write-Host "  4. Watch OSRM process the data (10-20 min first run):"
Write-Host "     docker logs -f rvc_osrm"
Write-Host ""
Write-Host "Coverage after setup: GA, TN, KY, AL, SC, NC" -ForegroundColor Green
Write-Host "KY to GA routing: ACCURATE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""