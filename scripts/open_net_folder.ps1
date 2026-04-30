param([string]$url)

# Браузер может добавить / после хоста: opennet://open/?path или opennet://open?path
$encoded = $url -replace '^opennet://open/\?', '' -replace '^opennet://open\?', ''

# UTF-8 decode (кириллица, пробелы, скобки)
$path = [System.Uri]::UnescapeDataString($encoded)

if ($path -ne '' -and $path -notmatch '^opennet://') {
    Start-Process explorer.exe -ArgumentList $path
}
