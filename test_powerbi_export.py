#!/usr/bin/env python3
"""
Тестовый скрипт для проверки powerbi_export.py
Проверяет импорты, классы и базовую логику без подключения к Oracle.
"""
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("ТЕСТИРОВАНИЕ powerbi_export.py")
print("=" * 60)

# ---------------------------------------------------------------------------
# 1. Проверка импорта библиотек
# ---------------------------------------------------------------------------
print("\n1. Проверка импорта библиотек...")

try:
    import pandas as pd
    print(f"   pandas {pd.__version__}: OK")
except ImportError as e:
    print(f"   pandas: ОШИБКА - {e}")
    sys.exit(1)

try:
    from sqlglot import exp, parse_one
    print(f"   sqlglot: OK")
except ImportError as e:
    print(f"   sqlglot: ОШИБКА - {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print(f"   python-dotenv: OK")
except ImportError as e:
    print(f"   python-dotenv: ОШИБКА - {e}")
    sys.exit(1)

try:
    import cx_Oracle
    print(f"   cx_Oracle: OK")
except ImportError:
    print(f"   cx_Oracle: не установлен (пропускаем)")

# ---------------------------------------------------------------------------
# 2. Импорт модуля powerbi_export через exec (чтобы избежать проблем с dataclasses)
# ---------------------------------------------------------------------------
print("\n2. Загрузка powerbi_export.py...")

# Читаем файл и выполняем в отдельном namespace
with open('powerbi_export.py', encoding='utf-8') as f:
    source = f.read()

# Создаём namespace и выполняем код
namespace = {'__file__': os.path.abspath('powerbi_export.py')}
exec(source, namespace)

# Проверяем наличие всех ключевых классов
classes_to_check = [
    'TableType', 'ColumnMetadata', 'TableInfo', 'SQLMetadata',
    'SQLDialect', 'dialect_to_sqlglot',
    'SQLPreprocessor',
    'ScopeInfo', 'DetailedColumnAnalyzer', 'CALCULATION_NODES',
    'ParserStrategy', 'SQLGlotParserStrategy',
    'normalize_sql_for_parsing', 'parse_sql_with_dialect_auto',
    'extract_metadata_from_sql', 'process_dataframe_v2',
    'load_config', 'create_results_table', 'insert_results', 'main',
]

all_ok = True
for name in classes_to_check:
    if name in namespace:
        print(f"   {name}: OK")
    else:
        print(f"   {name}: НЕ НАЙДЕН")
        all_ok = False

if not all_ok:
    print("\nОШИБКА: не все классы загружены!")
    sys.exit(1)

# Извлекаем ссылки на классы для удобства
TableType = namespace['TableType']
ColumnMetadata = namespace['ColumnMetadata']
TableInfo = namespace['TableInfo']
SQLMetadata = namespace['SQLMetadata']
SQLDialect = namespace['SQLDialect']
dialect_to_sqlglot = namespace['dialect_to_sqlglot']
SQLPreprocessor = namespace['SQLPreprocessor']
normalize_sql_for_parsing = namespace['normalize_sql_for_parsing']
parse_sql_with_dialect_auto = namespace['parse_sql_with_dialect_auto']
extract_metadata_from_sql = namespace['extract_metadata_from_sql']
process_dataframe_v2 = namespace['process_dataframe_v2']

# ---------------------------------------------------------------------------
# 3. Тест TableType
# ---------------------------------------------------------------------------
print("\n3. Тест TableType...")
assert TableType.TABLE.value == "Таблица"
assert TableType.SUBQUERY.value == "Подзапрос"
assert TableType.CTE.value == "CTE"
print("   OK")

# ---------------------------------------------------------------------------
# 4. Тест ColumnMetadata
# ---------------------------------------------------------------------------
print("\n4. Тест ColumnMetadata...")
col = ColumnMetadata(column_name="user_id", table="users")
assert col.name == "user_id"
assert col.table_name == "users"
col.normalize()
assert col.full_name == "users.user_id"
print(f"   full_name = '{col.full_name}': OK")

# ---------------------------------------------------------------------------
# 5. Тест TableInfo
# ---------------------------------------------------------------------------
print("\n5. Тест TableInfo...")
t = TableInfo(name="orders", schema="dbo")
t.add_alias("o")
assert "o" in t.aliases
assert t.get_aliases_str() == "o"
print(f"   aliases = '{t.get_aliases_str()}': OK")

# ---------------------------------------------------------------------------
# 6. Тест SQLMetadata
# ---------------------------------------------------------------------------
print("\n6. Тест SQLMetadata...")
meta = SQLMetadata(original_sql="SELECT * FROM test")
meta.add_column(col)
meta.add_table(t)
assert len(meta.columns) == 1
assert len(meta.tables) == 1
stats = meta.get_statistics()
assert stats['total_columns'] == 1
assert stats['total_tables'] == 1
print(f"   statistics = {stats}: OK")

# ---------------------------------------------------------------------------
# 7. Тест SQLDialect
# ---------------------------------------------------------------------------
print("\n7. Тест SQLDialect...")
assert SQLDialect.ORACLE.value == "oracle"
assert SQLDialect.SQLSERVER.value == "tsql"
assert dialect_to_sqlglot(SQLDialect.ORACLE) == "oracle"
assert dialect_to_sqlglot(SQLDialect.SQLSERVER) == "tsql"
print("   OK")

# ---------------------------------------------------------------------------
# 8. Тест SQLPreprocessor
# ---------------------------------------------------------------------------
print("\n8. Тест SQLPreprocessor...")
prep = SQLPreprocessor(dialect=SQLDialect.ORACLE)

# Тест удаления комментариев
sql1 = "SELECT * FROM t -- comment"
result1 = prep.preprocess(sql1)
assert 'comment' not in result1, f"Комментарий не удалён: {result1}"
print(f"   Комментарии: OK")

# Тест CONVERT -> CAST
sql2 = "SELECT CONVERT(datetime, date_col) FROM t"
result2 = prep.preprocess(sql2)
assert 'CAST' in result2.upper(), f"CONVERT не заменён: {result2}"
print(f"   CONVERT->CAST: OK")

# Тест TO_DATE
sql3 = "SELECT TO_DATE('2024-01-01', 'YYYY-MM-DD') FROM t"
result3 = prep.preprocess(sql3)
assert 'CAST' in result3.upper(), f"TO_DATE не заменён: {result3}"
print(f"   TO_DATE->CAST: OK")

# Тест валидации
valid, err = prep.validate_sql("SELECT * FROM t")
assert valid == True
valid, err = prep.validate_sql("")
assert valid == False
print(f"   validate_sql: OK")

# ---------------------------------------------------------------------------
# 9. Тест normalize_sql_for_parsing
# ---------------------------------------------------------------------------
print("\n9. Тест normalize_sql_for_parsing...")

# Тест: одна строка с двойными пробелами
sql_oneline = "select  t,  t2  from  tt  where  t.id = 1"
normalized = normalize_sql_for_parsing(sql_oneline)
assert '\n' in normalized, f"Нет переносов строк: {repr(normalized)}"
print(f"   Исходный:  {repr(sql_oneline[:60])}")
print(f"   Результат: {repr(normalized[:80])}")

# Тест: уже многострочный SQL не должен меняться
sql_multiline = "select t\nt2\nfrom tt"
normalized2 = normalize_sql_for_parsing(sql_multiline)
assert normalized2 == sql_multiline, f"Многострочный изменился: {repr(normalized2)}"
print(f"   Многострочный не изменился: OK")

# Тест: пустой SQL
assert normalize_sql_for_parsing("") == ""
print(f"   Пустой SQL: OK")

# ---------------------------------------------------------------------------
# 10. Тест parse_sql_with_dialect_auto
# ---------------------------------------------------------------------------
print("\n10. Тест parse_sql_with_dialect_auto...")

# Простой Oracle SQL
simple_sql = "SELECT t.name, t.id FROM users t WHERE t.id = 1"
ast, dialect = parse_sql_with_dialect_auto(simple_sql)
assert ast is not None, f"AST не получен для: {simple_sql}"
assert dialect is not None, f"Диалект не определён"
print(f"   SQL: '{simple_sql[:50]}...' -> dialect={dialect}: OK")

# T-SQL с квадратными скобками
tsql_sql = "SELECT [t].[name] FROM [dbo].[users] [t]"
ast2, dialect2 = parse_sql_with_dialect_auto(tsql_sql)
assert ast2 is not None, f"AST не получен для TSQL"
print(f"   TSQL: '{tsql_sql}' -> dialect={dialect2}: OK")

# PostgreSQL
pg_sql = "SELECT t.name::text FROM users t"
ast3, dialect3 = parse_sql_with_dialect_auto(pg_sql)
assert ast3 is not None, f"AST не получен для PostgreSQL"
print(f"   PostgreSQL: '{pg_sql}' -> dialect={dialect3}: OK")

# ---------------------------------------------------------------------------
# 11. Тест extract_metadata_from_sql
# ---------------------------------------------------------------------------
print("\n11. Тест extract_metadata_from_sql...")

test_sql = "SELECT u.id, u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE o.total > 100"
mappings, dialect = extract_metadata_from_sql(test_sql)
assert len(mappings) > 0, f"Нет метаданных для: {test_sql}"
print(f"   SQL: '{test_sql[:60]}...'")
print(f"   Диалект: {dialect}")
print(f"   Найдено колонок: {len(mappings)}")
for m in mappings:
    print(f"     - {m['col_full_name']} (таблица: {m['table_name']}, тип: {m['table_type']})")

# ---------------------------------------------------------------------------
# 12. Тест process_dataframe_v2
# ---------------------------------------------------------------------------
print("\n12. Тест process_dataframe_v2...")

test_data = pd.DataFrame({
    'REP_ID': [1, 2],
    'DP_ID': ['DP1', 'DP2'],
    'SQL_TEXT': [
        'SELECT  id,  name  FROM  users  WHERE  id = 1',
        'SELECT  t.col1,  t.col2  FROM  schema.table  t',
    ]
})

result_df = process_dataframe_v2(test_data, sql_column='SQL_TEXT')
assert not result_df.empty, "DataFrame пустой"
print(f"   Входных записей: {len(test_data)}")
print(f"   Результирующих записей: {len(result_df)}")
print(f"   Колонки: {list(result_df.columns)}")
for _, row in result_df.iterrows():
    print(f"     KEY={row['KEY']}, col={row['col_name']}, table={row['table_name']}, dialect={row['dialect']}")

# ---------------------------------------------------------------------------
# 13. Тест обработки ошибок парсинга
# ---------------------------------------------------------------------------
print("\n13. Тест обработки ошибок парсинга...")

bad_sql_df = pd.DataFrame({
    'REP_ID': [99],
    'DP_ID': ['BAD'],
    'SQL_TEXT': ['NOT A VALID SQL @@@ @@@'],
})

bad_result = process_dataframe_v2(bad_sql_df, sql_column='SQL_TEXT')
assert not bad_result.empty, "Должна быть запись об ошибке"
assert bad_result.iloc[0]['table_type'] == 'parse_error', f"Неверный тип ошибки: {bad_result.iloc[0]['table_type']}"
print(f"   SQL: 'NOT A VALID SQL' -> table_type={bad_result.iloc[0]['table_type']}: OK")

# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
print("=" * 60)