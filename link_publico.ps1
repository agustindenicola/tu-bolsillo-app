# Prende Tu Bolsillo (si hace falta), abre un link público gratis con Cloudflare y lo muestra.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
New-Item -ItemType Directory -Force datos | Out-Null
$cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$simular = $env:TB_SIMULAR_TUNEL -eq "1"   # solo para probar este script

function AppViva { try { Invoke-WebRequest http://127.0.0.1:8770/api/catalog -UseBasicParsing -TimeoutSec 2 | Out-Null; $true } catch { $false } }

Write-Host ""
Write-Host "  TU BOLSILLO - link publico" -ForegroundColor Cyan
Write-Host ""

# 1) la app
if (-not (AppViva)) {
    Write-Host "  Prendiendo la app..."
    $cmd = "set TUBOLSILLO_HTTPS=1&& set TUBOLSILLO_DEMO=1&& title Tu Bolsillo - app (NO CERRAR)&& python run.py"
    Start-Process cmd -ArgumentList "/k", $cmd -WorkingDirectory $here -WindowStyle Minimized
    for ($i = 0; $i -lt 40 -and -not (AppViva); $i++) { Start-Sleep 1 }
    if (-not (AppViva)) { Write-Host "  No se pudo prender la app. Mirá la ventana 'Tu Bolsillo - app'." -ForegroundColor Yellow; Read-Host "  Enter para cerrar"; exit 1 }
}
Write-Host "  App prendida." -ForegroundColor Green

# 2) el túnel
$log = Join-Path $here "datos\tunel.log"
Remove-Item $log -ErrorAction SilentlyContinue
if ($simular) {
    Set-Content $log "INF | https://prueba-falsa-123.trycloudflare.com |"
} else {
    if (-not (Test-Path $cf)) { Write-Host "  Falta instalar Cloudflare Tunnel (cloudflared)." -ForegroundColor Yellow; Read-Host "  Enter para cerrar"; exit 1 }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force   # un solo túnel a la vez
    Start-Process $cf -ArgumentList "tunnel", "--no-autoupdate", "--logfile", "`"$log`"", "--url", "http://127.0.0.1:8770" -WindowStyle Minimized
}
Write-Host "  Creando el link, esperá unos segundos..."
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep 1
    if (Test-Path $log) {
        $m = [regex]::Match((Get-Content $log -Raw), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($m.Success) { $url = $m.Value }
    }
}
if (-not $url) { Write-Host "  No se pudo crear el link. Revisá internet y volvé a abrir el archivo." -ForegroundColor Yellow; Read-Host "  Enter para cerrar"; exit 1 }

# 3) mostrarlo, copiarlo, guardarlo y abrirlo
Set-Content (Join-Path $here "LINK.txt") $url
try { Set-Clipboard $url } catch {}
if (-not $simular) { Start-Sleep 4; Start-Process $url }
Write-Host ""
Write-Host "  ==========================================================" -ForegroundColor Green
Write-Host "   TU LINK PARA COMPARTIR:" -ForegroundColor Green
Write-Host ""
Write-Host "   $url" -ForegroundColor White
Write-Host ""
Write-Host "   Ya esta copiado: pegalo con Ctrl+V en WhatsApp." -ForegroundColor Green
Write-Host "   Tambien quedo guardado en el archivo LINK.txt." -ForegroundColor Green
Write-Host "  ==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Anda mientras la compu este prendida. No cierres las ventanas"
Write-Host "  minimizadas 'Tu Bolsillo - app' ni la de cloudflared."
Write-Host "  Cada vez que abras el archivo, el link cambia."
Write-Host ""
# 4) mientras esta ventana esté abierta, la compu no se suspende (la pantalla sí puede apagarse)
if ($simular) { exit 0 }
Add-Type -Namespace TB -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[TB.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
Write-Host "  Mientras esta ventana este abierta, la compu NO se va a suspender." -ForegroundColor Cyan
Write-Host "  Para apagar el link: cerra esta ventana y las minimizadas." -ForegroundColor Cyan
Write-Host ""
while ($true) {
    Start-Sleep 60
    if (-not (AppViva)) { Write-Host ("  [" + (Get-Date -Format HH:mm) + "] Ojo: la app no responde. Volve a abrir el archivo.") -ForegroundColor Yellow }
    else {
        # Cloudflare a veces da de baja los links gratis: si pasa, se crea uno nuevo solo
        $vencido = (Test-Path $log) -and ((Get-Content $log -Tail 5 -ErrorAction SilentlyContinue) -match "Tunnel not found")
        if ($vencido -or -not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
            Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
            Remove-Item $log -ErrorAction SilentlyContinue
            Start-Process $cf -ArgumentList "tunnel", "--no-autoupdate", "--logfile", "`"$log`"", "--url", "http://127.0.0.1:8770" -WindowStyle Minimized
            $nuevo = $null
            for ($i = 0; $i -lt 60 -and -not $nuevo; $i++) {
                Start-Sleep 1
                if (Test-Path $log) { $m = [regex]::Match((Get-Content $log -Raw), "https://[a-z0-9-]+\.trycloudflare\.com"); if ($m.Success) { $nuevo = $m.Value } }
            }
            if ($nuevo) {
                Set-Content (Join-Path $here "LINK.txt") $nuevo
                try { Set-Clipboard $nuevo } catch {}
                Write-Host ("  [" + (Get-Date -Format HH:mm) + "] Cloudflare corto el link anterior. LINK NUEVO (ya copiado): $nuevo") -ForegroundColor Yellow
            } else { Write-Host ("  [" + (Get-Date -Format HH:mm) + "] Ojo: no se pudo crear un link nuevo. Volve a abrir el archivo.") -ForegroundColor Yellow }
        }
    }
}
