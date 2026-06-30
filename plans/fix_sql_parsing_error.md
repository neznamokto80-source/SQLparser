# План исправления ошибки парсинга SQL-запроса

## Проблема

Следующий SQL-запрос не парсится с диалектом ORACLE:

```sql
SELECT
         Bills.doc_number,
         Bills.doc_date,
         CONVERT(varchar(30), BillStockMoveStock.id)
FROM Bills WHERE 1=1
         AND BillDetailsItemStates.state_code NOT IN ('DEL' )
         AND Bills.doc_date > '09/01/2016 00:0:0'
      AND Bills.doc_date <= '10/01/2016 00:0:0'
```

## Корневые причины

### Причина 1: CONVERT(varchar(30), BillStockMoveStock.id) не заменяется на CAST

Паттерн на строках 78-81 в [`core/sql_preprocessor.py`](core/sql_preprocessor.py:78):

```python
(r"\bCONVERT\s*\(\s*(var)?char\s*\(\s*\d+\s*\)\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\2 AS \1char)"),
```

Проблема: `([^,]+)` — жадный захват любого символа кроме запятой. Для `CONVERT(varchar(30), BillStockMoveStock.id)`:
- `([^,]+)` захватывает `BillStockMoveStock.id)` — **включая закрывающую скобку** `)`, потому что `)` не является запятой
- Затем паттерн ожидает `\s*\)` в конце, но скобка уже захвачена
- В результате CONVERT **не заменяется** на CAST
- sqlglot с диалектом Oracle не знает функцию CONVERT → ошибка парсинга

**Аналогичная проблема** во всех паттернах CONVERT (строки 70-82), где второй аргумент захватывается через `([^,]+)`.

### Причина 2: Пробел внутри NOT IN ('DEL' )

В строке `AND BillDetailsItemStates.state_code NOT IN ('DEL' )` есть лишний пробел между `'DEL'` и `)`. sqlglot с диалектом Oracle может не принять пробел перед `)` в списке IN.

## Детальный план изменений

### Шаг 1: Исправить `_replace_convert_functions` — исключить `)` из захвата второго аргумента

В файле [`core/sql_preprocessor.py`](core/sql_preprocessor.py:68), метод `_replace_convert_functions`:

**Проблема:** `([^,]+)` захватывает `)` как часть второго аргумента.

**Решение:** Заменить `([^,]+)` на `([^,)]+)` во всех паттернах CONVERT. Это заставит захват останавливаться на `)`, а не включать её.

Изменяемые паттерны:

| Строка | Было | Стало |
|--------|------|-------|
| 70 | `([^,]+)` | `([^,)]+)` |
| 71 | `([^,]+)` | `([^,)]+)` |
| 72 | `([^,]+)` | `([^,)]+)` |
| 73 | `([^,]+)` | `([^,)]+)` |
| 75 | `([^,]+)` | `([^,)]+)` |
| 79 | `([^,]+)` | `([^,)]+)` |
| 82 | `([^,]+)` | `([^,)]+)` |

### Шаг 2: Исправить `_fix_common_issues` — удаление пробелов перед `)`

В файле [`core/sql_preprocessor.py`](core/sql_preprocessor.py:165), метод `_fix_common_issues`:

Добавить перед `return sql.strip()`:
```python
sql = re.sub(r'\s+\)', ')', sql)
```

Это удалит лишние пробелы перед `)` во всём запросе, включая `NOT IN ('DEL' )` → `NOT IN ('DEL')`.

### Шаг 3: Обновить тесты

В файле [`tests/test_sql_preprocessor.py`](tests/test_sql_preprocessor.py):

Добавить тесты:

```python
def test_preprocessor_handles_convert_with_dotted_column():
    """CONVERT с varchar и именем колонки, содержащим точку."""
    sql = "SELECT CONVERT(varchar(30), BillStockMoveStock.id) FROM Bills"
    result = SQLPreprocessor().preprocess(sql)
    assert "CONVERT" not in result.upper()
    assert "CAST" in result.upper()
    assert "BillStockMoveStock.id" in result


def test_preprocessor_handles_spaces_in_in_clause():
    """Пробел перед ) в NOT IN."""
    sql = "SELECT col FROM t WHERE col NOT IN ('DEL' )"
    result = SQLPreprocessor().preprocess(sql)
    assert "('DEL')" in result


def test_preprocessor_full_query():
    """Полный запрос из задачи."""
    sql = """SELECT
         Bills.doc_number,
         Bills.doc_date,
         CONVERT(varchar(30), BillStockMoveStock.id)
FROM Bills WHERE 1=1
         AND BillDetailsItemStates.state_code NOT IN ('DEL' )
         AND Bills.doc_date > '09/01/2016 00:0:0'
      AND Bills.doc_date <= '10/01/2016 00:0:0'"""
    result = SQLPreprocessor().preprocess(sql)
    assert "CONVERT" not in result.upper()
    assert "CAST" in result.upper()
    assert "('DEL')" in result
```

## Ожидаемый результат после preprocess

После исправлений препроцессор должен преобразовать запрос в:

```sql
SELECT Bills.doc_number, Bills.doc_date, CAST(BillStockMoveStock.id AS varchar(30)) FROM Bills WHERE 1=1 AND BillDetailsItemStates.state_code NOT IN ('DEL') AND Bills.doc_date > '09/01/2016 00:0:0' AND Bills.doc_date <= '10/01/2016 00:0:0'
```

## Проверка

1. Запустить существующие тесты: `python -m pytest tests/ -v`
2. Запустить новые тесты
3. Проверить, что sqlglot парсит результат без ошибок