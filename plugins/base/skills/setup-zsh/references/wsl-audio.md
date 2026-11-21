# Claude Code voice through PulseAudio on Windows (WSL)

Step 9 sends you here when the user wants the microphone for Claude Code voice to bypass
WSLg. `<this-skill-dir>` is the skill directory.

WSLg brings the Windows microphone into WSL over its RDP connection. When that link
fails (`audin_server_recv_data failed with error 1359` in `/mnt/wslg/wlog.log`), WSLg's
PulseAudio hangs: `pactl` gets "Connection refused", voice reports no audio, and only
`wsl --shutdown` recovers ([wslg#1508](https://github.com/microsoft/wslg/issues/1508)).
It shows up after a few dictations, more often when a Windows dictation app such as
OpenWhispr uses the microphone in between, and still happens on WSLg 1.0.79.

The fix runs [pulseaudio-win32](https://github.com/pgaskin/pulseaudio-win32) as the
Windows user, recording only, listening on `127.0.0.1:4713`. A `claude` wrapper in
`~/.zshrc` records through it when it answers and falls back to WSLg otherwise. Sound
output and every other program stay on WSLg.

## 1. Check what is there

```bash
wslinfo --networking-mode 2>/dev/null
APPDATA_WSL="$(wslpath "$(cd /mnt/c && cmd.exe /c 'echo %APPDATA%' 2>/dev/null | tr -d '\r')")"
test -f "/mnt/c/Program Files (x86)/PulseAudio/bin/pulseaudio.exe" && echo "pulseaudio-win32: INSTALLED" || echo "pulseaudio-win32: MISSING"
test -f "$APPDATA_WSL/pulseaudio-wsl/wsl.pa" && echo "config: OK" || echo "config: MISSING"
test -f "$APPDATA_WSL/Microsoft/Windows/Start Menu/Programs/Startup/PulseAudio for WSL.lnk" && echo "autostart: OK" || echo "autostart: MISSING"
grep -q '# >>> setup-zsh claude-pulse >>>' ~/.zshrc && echo "zsh wrapper: OK" || echo "zsh wrapper: MISSING"
```

The server must be reachable at Windows' `127.0.0.1`, which needs mirrored networking. If
the first line does not print `mirrored`, tell the user this needs
`networkingMode=mirrored` under `[wsl2]` in `%USERPROFILE%\.wslconfig` (then
`wsl --shutdown`) and skip the rest of this file.

Skip the sections whose part is already in place.

## 2. Install pulseaudio-win32 (the user, on Windows)

Give the user the download link and the installer choices:

- Download <https://github.com/pgaskin/pulseaudio-win32/releases/download/v5/pasetup.exe>
  (v5, 2021; unsigned, so SmartScreen may warn).
- Untick the **Windows Service** component. The service runs as LocalService, which has
  no access to sound devices (`Failed to open WaveOut ... device ID out of range` in
  `C:\ProgramData\PulseAudio\pulseaudio.log`), so it only offers a dummy device.

If the service was installed anyway, it holds port 4713; the user disables it in an
**admin** PowerShell:

```powershell
Stop-Service PulseAudio; Set-Service PulseAudio -StartupType Disabled
```

## 3. Config and start script

Copy both files into `%APPDATA%\pulseaudio-wsl` and start the server:

```bash
mkdir -p "$APPDATA_WSL/pulseaudio-wsl"
cp <this-skill-dir>/assets/wsl-audio/wsl.pa <this-skill-dir>/assets/wsl-audio/start.ps1 "$APPDATA_WSL/pulseaudio-wsl/"
(cd /mnt/c && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$APPDATA_WSL/pulseaudio-wsl/start.ps1")" </dev/null)
```

`wsl.pa` loads the Windows microphone (`module-waveout`, record only: with playback the
module fails whenever no speaker or headset is connected) and the TCP protocol for
`127.0.0.1` only. `start.ps1` starts `pulseaudio.exe` hidden unless it already runs, with
its log in `%APPDATA%\pulseaudio-wsl\pulseaudio.log`.

## 4. Verify

```bash
timeout 5 pactl --server=tcp:127.0.0.1:4713 info | grep 'Default Source'
timeout 3 parecord --server=tcp:127.0.0.1:4713 --channels=1 --rate=16000 --file-format=wav /tmp/pa-test.wav
python3 -I -c "import wave,array,sys; w=wave.open(sys.argv[1]); a=array.array('h',w.readframes(w.getnframes())); print('frames',len(a),'peak',max(map(abs,a)) if a else 0)" /tmp/pa-test.wav; rm -f /tmp/pa-test.wav
```

Expect `Default Source: wavein` and about 48000 frames. A peak near zero only means the
room was quiet. If `wavein` is missing, read the log named above and report it.

## 5. Start at logon (the user, normal PowerShell)

Creating a Startup shortcut may be blocked for you as a persistence change; give the user
this to run once. Windows then starts the server at every logon, independent of WSL:

```powershell
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'PulseAudio for WSL.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = 'powershell.exe'
$s.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$env:APPDATA\pulseaudio-wsl\start.ps1`""
$s.WindowStyle = 7; $s.Save()
```

## 6. zsh wrapper

Unless `~/.zshrc` contains `# >>> setup-zsh claude-pulse >>>`, append
`<this-skill-dir>/assets/zshrc/claude-pulse.zsh` at the end and check the syntax:

```bash
cat <this-skill-dir>/assets/zshrc/claude-pulse.zsh >> ~/.zshrc
zsh -n ~/.zshrc && echo "syntax ok"
```

Tell the user: new shells start `claude` with the Windows microphone while the server
answers (checked in at most a second), and fall back to WSLg when it does not. Claude
sessions resumed by the Herdr app go through the same wrapper. Running sessions keep their
old audio path until restarted.

## Uninstall

Remove the `setup-zsh claude-pulse` block from `~/.zshrc`, then on Windows delete the
Startup shortcut `PulseAudio for WSL.lnk` and `%APPDATA%\pulseaudio-wsl`, stop
`pulseaudio.exe`, and uninstall PulseAudio from Settings > Apps.
