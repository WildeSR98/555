"""
Тестовый скрипт для проверки работы FastAPI приложения.
Запускает приложение и делает тестовые запросы.
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from httpx import AsyncClient, ASGITransport

async def test_app():
    """Тестирование FastAPI приложения."""
    from web.main import app
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Тест главной страницы (редирект на login)
        print("Testing /login...")
        try:
            response = await client.get("/login", follow_redirects=False)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print("  OK: Страница login загружается")
            elif response.status_code == 500:
                print("  ERROR: Internal Server Error")
                print("  Detail:", response.text[:500])
            else:
                print("  Response:", response.text[:200])
        except Exception as e:
            print(f"  ERROR: {e}")
        
        # Тест API документации
        print("\nTesting /docs...")
        try:
            response = await client.get("/docs")
            print(f"  Status: {response.status_code}")
        except Exception as e:
            print(f"  ERROR: {e}")
        
        # Тест API эндпоинта
        print("\nTesting /api/dashboard/...")
        try:
            response = await client.get("/api/dashboard/")
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print("  OK: API работает")
                print("  Data:", str(response.json())[:200])
            else:
                print("  Error:", response.text[:200])
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Production Manager Web — Testing")
    print("=" * 60)
    print()
    asyncio.run(test_app())
