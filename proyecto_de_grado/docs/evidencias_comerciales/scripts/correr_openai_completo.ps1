# Evalua las 1061 citas con anotacion humana usando OpenAI (GPT-6.1 Sol), con las 4 tandas AL MISMO TIEMPO.
# Abre 4 ventanas pequenas (una por tanda); en total tarda unos 40 a 60 minutos y cuesta unos US$6.
# Se puede volver a correr: salta las tandas que ya terminaron.
# Uso:  powershell -ExecutionPolicy Bypass -File "D:\tmp\costos\correr_openai_completo.ps1"
# Correrlo cuando el piloto de 103 citas ya haya terminado.

$repo = "D:\Projects\Proyecto despliegue de soluciones"
$dir  = "D:\tmp\costos"
Set-Location $repo

# Clave nueva: se pide aqui y no se muestra al escribirla. Las 4 ventanas la heredan; no se guarda en ningun archivo.
$k = Read-Host "Clave NUEVA de OpenAI (no se muestra)" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $k).Password
$env:OPENAI_MODEL = "gpt-6.1-sol"

$procesos = @()
foreach ($i in 1..4) {
    $salida = "$dir\salida_openai_$i"
    if (Test-Path "$salida\results.jsonl") { Write-Host "Tanda $i ya estaba terminada, se salta."; continue }
    $script = "$dir\_tanda_openai_$i.ps1"
    $linea  = "Set-Location '$repo'; uv run python -m src.evaluation.commercial.orchestrate --mode openai --gold '$dir\completo_$i.jsonl' --allow-provisional --pricing '$dir\tarifas_openai.json' --request-delay-seconds 0 --output-dir '$salida'; Write-Host 'Tanda $i terminada. Puedes cerrar esta ventana.'; Start-Sleep -Seconds 5"
    Set-Content -Path $script -Value $linea -Encoding ASCII
    $procesos += Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $script -PassThru
    Write-Host ("[{0}] Tanda {1} lanzada." -f (Get-Date -Format "HH:mm:ss"), $i)
}
if ($procesos.Count -gt 0) {
    Write-Host "Esperando a que terminen las tandas (no cierres esta ventana)..."
    $procesos | Wait-Process
}
$hechas = @(1..4 | Where-Object { Test-Path "$dir\salida_openai_$_\results.jsonl" })
Write-Host ("Tandas con resultados: {0} de 4 ({1})" -f $hechas.Count, ($hechas -join ", "))
if ($hechas.Count -eq 4) { Write-Host "LISTO. Avisale a Claude para calcular costos y resultados." }
else { Write-Host "Faltan tandas. Vuelve a correr este mismo script y retoma las que faltan." }
Remove-Item "$dir\_tanda_openai_*.ps1" -ErrorAction SilentlyContinue
