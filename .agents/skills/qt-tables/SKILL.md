---
name: qt-tables
description: QTableWidget styling standards for Production Manager (PyQt6). Auto-fit columns to text length.
---

# Table Styling Standard (QTableWidget / QTreeWidget)

When creating or editing any table in the `appwin` project, these rules are **mandatory**.

## 1. Every column must have an explicit `setSectionResizeMode`

Never leave columns without an explicit mode. For **each** column, specify one of two modes:

```python
hdr = self.table.horizontalHeader()
hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # short data
hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # long data
```

## 2. Mode Selection

| Mode | When to use | Example columns |
| --- | --- | --- |
| `ResizeToContents` | Short, fixed-length text | ID, Code, Time, Date, Action, Status, Role |
| `Stretch` | Long or variable-length text | Name, Full Name, Device SN, Project, Workplace, Description |

## 3. Forbidden

- ❌ Using `Interactive` as the only mode (text gets clipped).
- ❌ Leaving columns without an explicit mode (default size is too small).
- ❌ Setting `Stretch` on all columns (short data stretches excessively).

## 4. Template

```python
# Example: table with 5 columns
self.table = QTableWidget()
self.table.setColumnCount(5)
self.table.setHorizontalHeaderLabels([
    'ID', 'Login', 'Full Name', 'Role', 'Status'
])

hdr = self.table.horizontalHeader()
hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Login
hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Full Name
hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Role
hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Status

self.table.setAlternatingRowColors(True)
self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
self.table.verticalHeader().setVisible(False)
```

## 5. Additional

- If a column contains a widget (action buttons), use `ResizeToContents`.
- After populating data, call `self.table.resizeRowsToContents()` to adjust row heights.
