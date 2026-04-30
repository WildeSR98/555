"""Генератор установочного bat-файла для протокола opennet://"""
import sys

vbs = r'\\192.168.106.29\PR_DEP\.apptools\open_net_folder.vbs'

lines = [
    '@echo off',
    ':: Install opennet:// protocol - run once per workstation',
    '',
    r'reg add "HKCU\SOFTWARE\Classes\opennet" /ve /d "URL:Open Network Folder" /f >nul',
    r'reg add "HKCU\SOFTWARE\Classes\opennet" /v "URL Protocol" /d "" /f >nul',
    f'reg add "HKCU\\SOFTWARE\\Classes\\opennet\\shell\\open\\command" /ve /d '
    f'"%SystemRoot%\\System32\\wscript.exe /B \\"{vbs}\\" \\"%%1\\"" /f >nul',
    '',
    'echo.',
    'echo [OK] Protocol opennet:// installed.',
    'echo     The Open Folder button now works in your browser.',
    'echo.',
    'pause',
]

bat = '\r\n'.join(lines) + '\r\n'

if len(sys.argv) > 1:
    # Записать в файл
    with open(sys.argv[1], 'w', encoding='cp866', errors='replace') as f:
        f.write(bat)
    print(f'Written to {sys.argv[1]}')
else:
    sys.stdout.buffer.write(bat.encode('cp866', errors='replace'))
