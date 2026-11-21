# Evalua las 1061 citas con anotacion humana usando Gemini, en 4 tandas seguidas.
# Se puede volver a correr: salta las tandas que ya terminaron y retoma desde la que fallo.
# Uso:  powershell -ExecutionPolicy Bypass -File "D:\tmp\costos\correr_todo.ps1"

$repo = "D:\Projects\Proyecto despliegue de soluciones"
$dir  = "D:\tmp\costos"
Set-Location $repo

# La clave se pide solo si no esta definida en esta ventana; al escribirla no se muestra en pantalla.
if (-not $env:GEMINI_API_KEY) {
    $k = Read-Host "Clave de Gemini (no se muestra)" -AsSecureString
    $env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $k).Password
}
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"

# Evita que el equipo se suspenda mientras corre (se revierte solo al terminar).
Add-Type -Namespace Win -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[Win.Power]::SetThreadExecutionState([uint32]2147483649) | Out-Null

$inicio = Get-Date
try {
    foreach ($i in 1..4) {
        $salida = "$dir\salida_gemini_$i"
        if (Test-Path "$salida\results.jsonl") {
            Write-Host "Tanda $i de 4 ya estaba terminada, se salta."
            continue
        }
        Write-Host ("[{0}] Empieza la tanda {1} de 4 (no mostrara nada hasta terminar, tarda unos 20 minutos)..." -f (Get-Date -Format "HH:mm:ss"), $i)
        uv run python -m src.evaluation.commercial.orchestrate --mode gemini --gold "$dir\completo_$i.jsonl" --allow-provisional --pricing "$dir\tarifas_gemini.json" --request-delay-seconds 1 --output-dir $salida
        if ($LASTEXITCODE -ne 0) {
            throw "La tanda $i fallo (codigo $LASTEXITCODE). Vuelve a correr este mismo script: retoma desde esta tanda."
        }
        Write-Host ("[{0}] Termino la tanda {1} de 4." -f (Get-Date -Format "HH:mm:ss"), $i)
    }
    $min = [math]::Round(((Get-Date) - $inicio).TotalMinutes)
    Write-Host "LISTO: las 4 tandas terminaron en $min minutos. Avisale a Claude para calcular costos y resultados."
}
finally {
    [Win.Power]::SetThreadExecutionState([uint32]2147483648) | Out-Null
}
