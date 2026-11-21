# Evalua con OpenAI (GPT-6.1 Sol): primero una prueba de 3 citas (9 llamadas) para ver el costo real,
# y si sale bien sigue con el piloto de 103 citas (309 llamadas).
# Se puede correr al mismo tiempo que la evaluacion de Gemini, en OTRA ventana de PowerShell.
# Uso:  powershell -ExecutionPolicy Bypass -File "D:\tmp\costos\correr_openai.ps1"

$repo = "D:\Projects\Proyecto despliegue de soluciones"
$dir  = "D:\tmp\costos"
Set-Location $repo

# La clave que estaba definida en el equipo esta VENCIDA (error 401). Se pide siempre una nueva; no se muestra al escribirla.
$k = Read-Host "Clave NUEVA de OpenAI (no se muestra)" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $k).Password
$env:OPENAI_MODEL = "gpt-6.1-sol"

# Corre el programa mostrando su salida en pantalla y devuelve SOLO el codigo de salida.
function Correr($gold, $salida) {
    uv run python -m src.evaluation.commercial.orchestrate --mode openai --gold $gold --allow-provisional --pricing "$dir\tarifas_openai.json" --request-delay-seconds 1 --output-dir $salida | Out-Host
    return [int]$LASTEXITCODE
}

# 1. Prueba pequena (siempre se rehace)
$mini = "$dir\salida_openai_mini"
if (Test-Path $mini) { Remove-Item $mini -Recurse -Force }
Write-Host "Prueba de 3 citas con OpenAI (unos 30 segundos)..."
[void](Correr "$dir\piloto_mini.jsonl" $mini)

if (-not (Test-Path "$mini\results.jsonl")) { throw "La prueba no genero resultados. Pegame el mensaje de arriba, sin la clave." }
$filas = @(Get-Content "$mini\results.jsonl" | ForEach-Object { $_ | ConvertFrom-Json })
$ok    = @($filas | Where-Object { $_.status -eq "ok" }).Count
if ($ok -ne $filas.Count) {
    $e = ($filas | Where-Object { $_.status -ne "ok" } | Select-Object -First 1).error
    throw ("Hubo llamadas con error en la prueba; no se sigue. Primer error: " + $e)
}
$costo = ($filas | Measure-Object -Property estimated_cost_usd -Sum).Sum
$porLlamada = $costo / $filas.Count
Write-Host ('Prueba: {0} de {1} llamadas bien | costo US${2:N5} | por llamada US${3:N5}' -f $ok, $filas.Count, $costo, $porLlamada)
Write-Host ('Proyeccion: piloto de 309 llamadas = US${0:N2} (~{1:N0} COP)' -f ($porLlamada*309), ($porLlamada*309*4000))
Write-Host ('Proyeccion: 1061 citas completas (3183 llamadas) = US${0:N2} (~{1:N0} COP)' -f ($porLlamada*3183), ($porLlamada*3183*4000))
Write-Host "Si el costo del piloto te parece alto, presiona Ctrl+C ahora. Si no, sigue solo en 15 segundos..."
Start-Sleep -Seconds 15

# 2. Piloto de 103 citas
$piloto = "$dir\salida_openai_piloto"
if (-not (Test-Path "$piloto\results.jsonl")) {
    Write-Host "Empieza el piloto de 103 citas (no mostrara nada hasta terminar, unos 10 minutos)..."
    [void](Correr "$dir\piloto_comerciales.jsonl" $piloto)
}
if (Test-Path "$piloto\results.jsonl") { Write-Host "LISTO. Avisale a Claude para calcular costos y resultados." }
else { throw "El piloto no genero resultados. Vuelve a correr este mismo script." }
