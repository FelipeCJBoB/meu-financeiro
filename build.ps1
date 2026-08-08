.venv\Scripts\pyinstaller.exe --name MeuFinanceiro --noconfirm --windowed --onefile --add-data ".venv\lib\site-packages\nicegui;nicegui" run.py
Write-Host "Executavel gerado em dist\MeuFinanceiro.exe"
