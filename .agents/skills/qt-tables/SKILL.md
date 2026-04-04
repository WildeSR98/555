---
name: qt-tables
description: Правила оформления QTableWidget в проекте Production Manager (PyQt6). Автоподгонка колонок под длину текста.
---

# Стандарт оформления таблиц (QTableWidget / QTreeWidget)

При создании или редактировании любой таблицы в проекте `appwin` **обязательно** соблюдать следующие правила.

## 1. Каждая колонка должна иметь явный `setSectionResizeMode`

Никогда не оставлять колонки без явного режима. Для **каждой** колонки нужно указать один из двух режимов:

```python
hdr = self.table.horizontalHeader()
hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # короткие данные
hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # длинные данные
```

## 2. Выбор режима

| Режим | Когда использовать | Примеры колонок |
| --- | --- | --- |
| `ResizeToContents` | Короткий, фиксированный текст | ID, Код, Время, Дата, Действие, Статус, Роль |
| `Stretch` | Длинный или переменный текст | Название, ФИО, SN устройства, Проект, Рабочее место, Описание |

## 3. Запрещено

- ❌ Использовать `Interactive` как единственный режим (текст обрезается).
- ❌ Оставлять колонки без явного режима (размер по умолчанию слишком мал).
- ❌ Ставить `Stretch` на все колонки (тогда короткие данные растягиваются избыточно).

## 4. Шаблон

```python
# Пример: таблица с 5 колонками
self.table = QTableWidget()
self.table.setColumnCount(5)
self.table.setHorizontalHeaderLabels([
    'ID', 'Логин', 'ФИО', 'Роль', 'Статус'
])

hdr = self.table.horizontalHeader()
hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Логин
hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # ФИО
hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Роль
hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Статус

self.table.setAlternatingRowColors(True)
self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
self.table.verticalHeader().setVisible(False)
```

## 5. Дополнительно

- Если в колонке размещается виджет (кнопки управления), используй `ResizeToContents`.
- После заполнения данных можно вызвать `self.table.resizeRowsToContents()` для подгонки высоты строк.
