# Start PulseAudio for WSL as the current user, hidden, unless it already runs.
if (Get-Process pulseaudio -ErrorAction SilentlyContinue) { exit 0 }
$dir = Join-Path $env:APPDATA 'pulseaudio-wsl'
Start-Process -WindowStyle Hidden -FilePath 'C:\Program Files (x86)\PulseAudio\bin\pulseaudio.exe' `
  -ArgumentList '-n', '-F', "`"$dir\wsl.pa`"", '--exit-idle-time=-1', "--log-target=`"file:$dir\pulseaudio.log`""
