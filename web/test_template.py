"""
Простой тест для проверки работы login страницы.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем шаблон напрямую через Jinja2
env = Environment(loader=FileSystemLoader(str(BASE_DIR / "web" / "templates")))

try:
    template = env.get_template("login.html")
    print("Template loaded successfully!")
    
    # Рендерим с mock данными
    class MockURL:
        path = "/login"
    
    class MockRequest:
        url = MockURL()
        session = {}
    
    result = template.render(request=MockRequest(), error=None)
    print(f"Template rendered! Length: {len(result)}")
    print("First 200 chars:")
    print(result[:200])
    
except Exception as e:
    import traceback
    print("ERROR:")
    traceback.print_exc()
