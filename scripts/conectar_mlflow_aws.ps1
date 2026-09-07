$InstanceId = "i-03aa657aecc9ebcd1"

Write-Host "Buscando IP actual de la EC2..."

$PublicIP = aws ec2 describe-instances `
    --instance-ids $InstanceId `
    --query "Reservations[0].Instances[0].PublicIpAddress" `
    --output text

if (-not $PublicIP -or $PublicIP -eq "None") {
    Write-Host "ERROR: No se encontró una IP pública para la EC2."
    exit 1
}

$env:MLFLOW_TRACKING_URI = "http://${PublicIP}:8050"

Write-Host ""
Write-Host "EC2 detectada: $PublicIP"
Write-Host "MLFLOW_TRACKING_URI configurada:"
Write-Host $env:MLFLOW_TRACKING_URI
Write-Host ""

$test = Test-NetConnection $PublicIP -Port 8050 -WarningAction SilentlyContinue

if ($test.TcpTestSucceeded) {
    Write-Host "MLflow está disponible en:"
    Write-Host $env:MLFLOW_TRACKING_URI
}
else {
    Write-Host "MLflow todavía no responde en el puerto 8050."
}
