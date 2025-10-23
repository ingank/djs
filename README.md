# DJ-Suite (`djs`)

CLI zur modularen DJ-Suite

## 1) Entwicklung (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate
pip install -e ".[dev]"
```

## 2) Tests
```powershell
pytest -q
```

## 3) CLI
```powershell
djs --help
djs -v foo 10 --mult 3
djs -vv --log-file djs.log bar --name Alice
djs --config .\example.config.toml foo 5
```

Beispiel `example.config.toml`:
```toml
# einfache Option, wird ins AppConfig.limit übernommen
limit = 42
```

## 4) Build
```powershell
pip install build
python -m build
Get-ChildItem dist\
```
