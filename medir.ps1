# Uso (desde la carpeta del proyecto, con Docker corriendo):
#   .\medir.ps1 -N 4 -G 2            # N = valor elegido en la calibracion, G = procesos por grupo (hibrido)
#   .\medir.ps1 -N 4 -G 2 -Rep 3
# Ejecuta cada version Rep veces, calcula la mediana y la aceleracion. Guarda resultados_medicion.txt
param(
    [Parameter(Mandatory = $true)][int]$N,
    [int]$G = 2,
    [int]$Rep = 3
)

$inv = [Globalization.CultureInfo]::InvariantCulture
$img = "augustosalazar/slim-mpi:2"
$flags = "--allow-run-as-root --use-hwthread-cpus --oversubscribe"

$casos = [ordered]@{
    "Secuencial"       = "python /app/baseline_secuencial.py --all"
    "MPI por tableros" = "mpiexec $flags -n $N python /app/mpi_por_tableros/mpi_tableros.py --all"
    "MPI por ramas"    = "mpiexec $flags -n $N python /app/mpi_por_ramas/mpi_ramas.py --all"
    "MPI hibrido"      = "mpiexec $flags -n $N python /app/mpi_hibrido/mpi_hibrido.py --all --grupo $G"
}

function Mediana($v) {
    $s = $v | Sort-Object
    $m = [int][math]::Floor($s.Count / 2)
    if ($s.Count % 2) { return $s[$m] } else { return ($s[$m - 1] + $s[$m]) / 2 }
}

$medianas = @{}
$lineas = @("N=$N, G=$G, repeticiones=$Rep", "")
foreach ($nombre in $casos.Keys) {
    $tiempos = @()
    for ($i = 1; $i -le $Rep; $i++) {
        Write-Host "$nombre - ejecucion $i de $Rep ..."
        $cmd = "docker run --rm -v `"${PWD}:/app`" $img $($casos[$nombre])"
        $salida = Invoke-Expression $cmd 2>&1 | Out-String
        if ($salida -match "Tiempo total(?: real)?: ([\d\.]+)") {
            $t = [double]::Parse($Matches[1], $inv)
            $tiempos += $t
            Write-Host ("  {0:N3} s" -f $t)
        } else {
            Write-Host "  No se encontro el tiempo total. Salida:"; Write-Host $salida
        }
    }
    if ($tiempos.Count -gt 0) {
        $medianas[$nombre] = Mediana $tiempos
        $lineas += ("{0}: {1} -> mediana {2:N3} s" -f $nombre, (($tiempos | ForEach-Object { $_.ToString("N3", $inv) }) -join " | "), $medianas[$nombre])
    }
}

$lineas += ""
$lineas += "| Implementacion | Procesos | Mediana (s) | Aceleracion |"
$lineas += "| --- | ---: | ---: | ---: |"
$base = $medianas["Secuencial"]
foreach ($nombre in $casos.Keys) {
    if ($medianas.ContainsKey($nombre)) {
        $p = if ($nombre -eq "Secuencial") { 1 } else { $N }
        $lineas += ("| {0} | {1} | {2} | {3} |" -f $nombre, $p, $medianas[$nombre].ToString("N3", $inv), ($base / $medianas[$nombre]).ToString("N2", $inv))
    }
}
$lineas | Tee-Object -FilePath resultados_medicion.txt
