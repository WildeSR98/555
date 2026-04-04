"""
Скрипт сборки .exe через PyInstaller.
Запуск: python build.py
"""

import subprocess
import sys
import os


def build():
    """Сборка приложения в один .exe файл."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, 'src', 'main.py')
    icon_path = os.path.join(base_dir, 'assets', 'icon.ico')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconsole',
        '--onefile',
        '--name=ProductionManager',
        f'--add-data={os.path.join(base_dir, ".env")};.',
    ]

    # Добавляем иконку, если существует
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')

    cmd.append(main_script)

    print('🔨 Запуск сборки...')
    print(f'   Команда: {" ".join(cmd)}')
    print()

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        print()
        print('✅ Сборка успешна!')
        print(f'   Файл: {os.path.join(base_dir, "dist", "ProductionManager.exe")}')
    else:
        print()
        print('❌ Ошибка сборки')
        sys.exit(1)


if __name__ == '__main__':
    build()
