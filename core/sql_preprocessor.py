"""
SQL preprocessor for cleaning and normalizing SQL statements before parsing.
"""

from __future__ import annotations

import re
from typing import Optional

from .sql_dialect import SQLDialect


class SQLPreprocessor:
    """Preprocessor for SQL statements."""

    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        """
        Initialize SQL preprocessor.

        Args:
            dialect: SQL dialect to use for preprocessing (default: ORACLE).
        """
        self.dialect = dialect

    def preprocess(self, sql: str) -> str:
        """
        Clean and normalize SQL statement.

        Performs the following steps:
        - Remove comments (single‑line `--` and multi‑line `/* */`)
        - Replace CONVERT functions with CAST
        - Replace TO_DATE functions with CAST('2000-01-01' AS DATE)
        - Replace variable functions (e.g., @func()) with empty string
        - Handle star operator (`*`) to avoid parsing errors
        - Normalize identifier quoting (square brackets to dialect‑appropriate quotes)
        - Fix common whitespace and punctuation issues

        Args:
            sql: Raw SQL string.

        Returns:
            Preprocessed SQL string ready for parsing.
        """
        if not sql:
            return sql

        sql = self._remove_comments(sql)
        sql = self._replace_convert_functions(sql)
        sql = self._replace_to_date_functions(sql)
        sql = self._replace_variable_functions(sql)
        sql = self._handle_star_operator(sql)
        sql = self._remove_square_brackets(sql)
        sql = self._fix_common_issues(sql)
        return sql

    def _remove_comments(self, sql: str) -> str:
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        return sql.strip()

    def _apply_patterns(self, sql: str, patterns: list[tuple[str, str]]) -> str:
        """Apply multiple regex substitutions sequentially."""
        result = sql
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _replace_convert_functions(self, sql: str) -> str:
        convert_patterns = [
            (r"\bCONVERT\s*\(\s*datetime\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime)"),
            (r"\bCONVERT\s*\(\s*date\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS date)"),
            (r"\bCONVERT\s*\(\s*smalldatetime\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS smalldatetime)"),
            (r"\bCONVERT\s*\(\s*datetime2\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime2)"),
            (
                r"\bCONVERT\s*\(\s*(numeric|decimal)\s*\(\s*\d+\s*,\s*\d+\s*\)\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)",
                r"CAST(\2 AS \1)",
            ),
            (
                r"\bCONVERT\s*\(\s*(var)?char\s*\(\s*\d+\s*\)\s*,\s*([^,]+)\s*(?:,\s*\d+\s*)?\)",
                r"CAST(\2 AS \1char)",
            ),
            (r"\bCONVERT\s*\(\s*(\w+)\s*,\s*([^,]+)\s*\)", r"CAST(\2 AS \1)"),
        ]
        return self._apply_patterns(sql, convert_patterns)

    def _replace_to_date_functions(self, sql: str) -> str:
        to_date_patterns = [
            (r"\bto_date\s*\(\s*@\w+\([^)]*\)\s*,\s*'([^']+)'\s*\)", r"CAST('2000-01-01' AS DATE)"),
            (r"\bto_date\s*\(\s*([^,]+)\s*,\s*'([^']+)'\s*\)", r"CAST('2000-01-01' AS DATE)"),
            (r"\bto_date\s*\(\s*([^)]+)\s*\)", r"CAST('2000-01-01' AS DATE)"),
        ]
        return self._apply_patterns(sql, to_date_patterns)

    def _replace_variable_functions(self, sql: str) -> str:
        pattern = r"@\w+\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
        return re.sub(pattern, "''", sql)

    def _handle_star_operator(self, sql: str) -> str:
        sql = re.sub(r"(\bSELECT\b)(\s+)\*", r"\1 _star_", sql, flags=re.IGNORECASE)
        sql = sql.replace(".*", "._star_")
        sql = re.sub(r",\s*\*\s*,", ",_star_,", sql)
        sql = re.sub(r"\*\s+(\bFROM\b)", r"_star_ \1", sql, flags=re.IGNORECASE)
        return sql

    def _remove_square_brackets(self, sql: str) -> str:
        """
        Replace square brackets outside string literals with appropriate quoting.
        For T-SQL keep brackets, for MySQL use backticks, for others double quotes.
        """
        # Состояния: 0 - вне кавычек, 1 - внутри одинарных кавычек, 2 - внутри двойных кавычек
        state = 0
        result = []
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "'" and state == 0:
                state = 1
                result.append(ch)
            elif ch == "'" and state == 1:
                # Проверяем экранирование: следующая кавычка?
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    result.append(ch)
                    i += 1
                    result.append(sql[i])
                else:
                    state = 0
                    result.append(ch)
            elif ch == '"' and state == 0:
                state = 2
                result.append(ch)
            elif ch == '"' and state == 2:
                if i + 1 < len(sql) and sql[i + 1] == '"':
                    result.append(ch)
                    i += 1
                    result.append(sql[i])
                else:
                    state = 0
                    result.append(ch)
            elif ch == '[' and state == 0:
                # Нашли открывающую скобку вне кавычек
                # Ищем закрывающую
                j = i + 1
                while j < len(sql) and sql[j] != ']':
                    j += 1
                if j < len(sql):
                    identifier = sql[i+1:j]
                    if self.dialect == SQLDialect.SQLSERVER:
                        result.append(f'[{identifier}]')
                    elif self.dialect == SQLDialect.MYSQL:
                        result.append(f'`{identifier}`')
                    else:
                        result.append(f'"{identifier}"')
                    i = j  # пропускаем закрывающую скобку
                else:
                    # нет закрывающей, оставляем как есть
                    result.append(ch)
            elif ch == ']' and state == 0:
                # Закрывающая скобка вне кавычек без открывающей? пропускаем
                result.append(ch)
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    def _fix_common_issues(self, sql: str) -> str:
        sql = re.sub(r"\s+", " ", sql)
        sql = sql.replace(", ,", ",")
        sql = sql.replace(",.", ",")
        sql = re.sub(r'^"', "", sql)
        return sql.strip()

    def validate_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        """
        Perform basic syntactic validation of a SQL statement.

        Checks:
        - SQL is not empty
        - Contains SELECT keyword (required for parsing)
        - If WHERE appears, FROM must also be present

        Args:
            sql: SQL string to validate.

        Returns:
            Tuple (is_valid, error_message). If valid, error_message is None.
        """
        if not sql:
            return False, "SQL запрос не может быть пустым"

        sql_upper = sql.upper()
        if "SELECT" not in sql_upper:
            return False, "SQL запрос должен содержать ключевое слово SELECT"
        if "FROM" not in sql_upper and "WHERE" in sql_upper:
            return False, "SQL запрос с WHERE должен содержать FROM"
        return True, None