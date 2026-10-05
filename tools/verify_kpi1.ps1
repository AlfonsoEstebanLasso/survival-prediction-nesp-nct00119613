<#
.SYNOPSIS
    Verificacion KPI-1 (reproducibilidad en entorno limpio) del TFG NESP-Oncology-20010145.

.DESCRIPTION
    Proposito
        Comprobar que el pipeline es reproducible en un entorno conda recien creado a
        partir de las versiones congeladas en environment.yml. Demuestra el KPI-1
        (reproducibilidad) del entregable D1.

    Entradas
        - environment.yml en la raiz del proyecto (versiones exactas congeladas).
        - Ficheros SAS crudos en el directorio indicado por -DataDir (por defecto
          "SAS dataset"). No se versionan; deben colocarse manualmente.
        - Opcional: kpi1_reference_hashes.txt (en la raiz) con los hashes de referencia.

    Salidas
        - Artefactos del ETL regenerados en output/ (dataset, diccionario, manifiesto).
        - kpi1_reference_hashes.txt (en la raiz, versionado): en la primera ejecucion fija
          la referencia; en las siguientes la compara.
        - Codigo de salida 0 si todo coincide y los tests pasan; 1 en caso contrario.

    Pasos
        1. Comprobar prerequisitos (conda y datos crudos disponibles).
        2. Crear (o recrear) un entorno conda limpio aislado del de trabajo.
        3. Ejecutar el ETL y, con -Full, el pipeline completo de modelado y evaluacion.
        4. Ejecutar la bateria de tests con pytest.
        5. Calcular el SHA-256 del dataset derivado y compararlo con la referencia.

.PARAMETER EnvName
    Nombre del entorno conda limpio. Por defecto tfg-nesp-verify, distinto del de
    trabajo (tfg-nesp) para no alterarlo.

.PARAMETER DataDir
    Directorio con los ficheros .sas7bdat. Por defecto "SAS dataset".

.PARAMETER Full
    Si se indica, ejecuta tambien el pipeline completo (modelos, evaluacion, sinteticos),
    no solo el ETL. Es mas lento (incluye busqueda de hiperparametros con Optuna).

.PARAMETER Recreate
    Si se indica, elimina el entorno limpio si ya existe y lo vuelve a crear desde cero.
    Recomendado para una verificacion estrictamente aislada: con PYTHONNOUSERSITE=1, la
    recreacion fuerza a instalar todas las dependencias dentro del entorno y no desde el
    user-site global.

.EXAMPLE
    .\verify_kpi1.ps1
    Verificacion rapida: entorno limpio, ETL y tests.

.EXAMPLE
    .\verify_kpi1.ps1 -Full -Recreate
    Verificacion completa, recreando el entorno desde cero.
#>

[CmdletBinding()]
param(
    [string] $EnvName  = "tfg-nesp-verify",
    [string] $DataDir  = "SAS dataset",
    [switch] $Full,
    [switch] $Recreate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# Aislamiento estricto: ignorar el user-site global (AppData\Roaming\Python) para que el
# entorno limpio use unicamente sus propios paquetes. Surte pleno efecto al crear el
# entorno con -Recreate, ya que fuerza a pip a instalar todas las dependencias dentro del
# entorno en lugar de darlas por satisfechas desde el user-site.
$env:PYTHONNOUSERSITE = "1"

function Write-Step  ([string] $m) { Write-Host "`n==== $m ====" -ForegroundColor Cyan }
function Write-Ok    ([string] $m) { Write-Host "  OK  $m" -ForegroundColor Green }
function Write-Fail  ([string] $m) { Write-Host "  XX  $m" -ForegroundColor Red }

# Ejecuta un comando dentro del entorno limpio con conda run y aborta si falla.
function Invoke-InEnv {
    param([Parameter(Mandatory)][string[]] $CmdArgs)
    & conda run --no-capture-output -n $EnvName @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail ("Fallo el comando: python " + ($CmdArgs -join " "))
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 1. Prerequisitos
# ---------------------------------------------------------------------------
Write-Step "1. Comprobando prerequisitos"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Fail "conda no esta en el PATH. Abre un Anaconda/Miniconda Prompt y reintenta."
    exit 1
}
Write-Ok "conda disponible"

if (-not (Test-Path "environment.yml")) {
    Write-Fail "No se encuentra environment.yml en la raiz del proyecto."
    exit 1
}
Write-Ok "environment.yml presente"

if (-not (Test-Path $DataDir)) {
    Write-Fail "No se encuentra el directorio de datos '$DataDir'. Coloca los .sas7bdat o usa -DataDir."
    exit 1
}
$sasCount = (Get-ChildItem -Path $DataDir -Filter *.sas7bdat -ErrorAction SilentlyContinue).Count
if ($sasCount -lt 1) {
    Write-Fail "No hay ficheros .sas7bdat en '$DataDir'."
    exit 1
}
Write-Ok "$sasCount ficheros .sas7bdat en '$DataDir'"

# ---------------------------------------------------------------------------
# 2. Entorno conda limpio
# ---------------------------------------------------------------------------
Write-Step "2. Preparando entorno conda limpio '$EnvName'"

$envExists = (& conda env list) -match "^\s*$([regex]::Escape($EnvName))\s"
if ($envExists -and $Recreate) {
    Write-Host "  Eliminando entorno previo '$EnvName' (--Recreate)..."
    & conda env remove -n $EnvName -y | Out-Null
    $envExists = $false
}

if ($envExists) {
    Write-Ok "El entorno '$EnvName' ya existe (usa -Recreate para forzar su recreacion)"
} else {
    Write-Host "  Creando entorno desde environment.yml (puede tardar varios minutos)..."
    & conda env create -f environment.yml -n $EnvName
    if ($LASTEXITCODE -ne 0) { Write-Fail "No se pudo crear el entorno '$EnvName'."; exit 1 }
    Write-Ok "Entorno '$EnvName' creado"
}

Write-Host "  Version de Python en el entorno:"
Invoke-InEnv @("python", "--version")

# ---------------------------------------------------------------------------
# 3. Ejecucion del pipeline
# ---------------------------------------------------------------------------
Write-Step "3. Ejecutando el ETL"
Invoke-InEnv @("python", "src/data/etl_nesp_nct00119613.py", "--data-dir", $DataDir, "--out", "output")
Write-Ok "ETL completado"

if ($Full) {
    Write-Step "3b. Ejecutando el pipeline completo (modelado, evaluacion, sinteticos)"
    $pipeline = @(
        "src/models/compare_models.py",
        "src/models/cox_baseline.py",
        "src/models/rsf_model.py",
        "src/models/xgb_model.py",
        "src/evaluation/eval_cox_final.py",
        "src/evaluation/robustness_cox.py",
        "src/evaluation/interpretability_cox.py",
        "src/data/synthetic_data.py"
    )
    foreach ($script in $pipeline) {
        Write-Host "  -> $script"
        Invoke-InEnv @("python", $script)
    }
    Write-Ok "Pipeline completo ejecutado"
} else {
    Write-Host "  (omitido el modelado; usa -Full para ejecutarlo)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 4. Tests
# ---------------------------------------------------------------------------
Write-Step "4. Ejecutando los tests (pytest)"
Invoke-InEnv @("python", "-m", "pytest", "tests/", "-q")
Write-Ok "Todos los tests pasan"

# ---------------------------------------------------------------------------
# 5. Comparacion de hashes (reproducibilidad byte a byte)
# ---------------------------------------------------------------------------
Write-Step "5. Verificando reproducibilidad por hash SHA-256"

$artefacts = @(
    "output/nesp_nct00119613_dataset.csv",
    "output/nesp_nct00119613_dictionary.csv"
)
$refFile = "kpi1_reference_hashes.txt"

$current = @{}
foreach ($a in $artefacts) {
    if (-not (Test-Path $a)) { Write-Fail "No se genero el artefacto esperado: $a"; exit 1 }
    $current[$a] = (Get-FileHash -Path $a -Algorithm SHA256).Hash
}

if (-not (Test-Path $refFile)) {
    # Primera ejecucion: fija la referencia.
    $lines = $artefacts | ForEach-Object { "{0}  {1}" -f $current[$_], $_ }
    Set-Content -Path $refFile -Value $lines -Encoding utf8
    Write-Ok "Referencia de hashes creada en $refFile (primera ejecucion)"
    foreach ($a in $artefacts) { Write-Host ("    {0}  {1}" -f $current[$a], $a) }
    Write-Host "`nVuelve a ejecutar este script (idealmente en otra maquina o entorno limpio) para comparar." -ForegroundColor Yellow
    exit 0
}

# Ejecuciones siguientes: compara con la referencia.
$reference = @{}
foreach ($line in (Get-Content $refFile | Where-Object { $_.Trim() -ne "" })) {
    $parts = $line -split "\s+", 2
    if ($parts.Count -eq 2) { $reference[$parts[1].Trim()] = $parts[0].Trim() }
}

$allMatch = $true
foreach ($a in $artefacts) {
    $cur = $current[$a]
    $ref = $reference[$a]
    if ($null -eq $ref) {
        Write-Host "  ??  $a sin referencia previa (hash actual: $cur)" -ForegroundColor Yellow
        $allMatch = $false
    } elseif ($cur -ieq $ref) {
        Write-Ok "$a coincide con la referencia"
    } else {
        Write-Fail "$a NO coincide"
        Write-Host "      referencia: $ref" -ForegroundColor Red
        Write-Host "      actual:     $cur" -ForegroundColor Red
        $allMatch = $false
    }
}

Write-Step "Resultado KPI-1"
if ($allMatch) {
    Write-Ok "Reproducibilidad confirmada: tests en verde y hashes identicos a la referencia."
    exit 0
} else {
    Write-Fail "Reproducibilidad NO confirmada: hay diferencias de hash. Revisa entorno y datos de entrada."
    exit 1
}
