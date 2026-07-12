"""
SQL preprocessor for cleaning and normalizing SQL statements before parsing.
"""

from __future__ import annotations

import re
from typing import Dict, Generator, Optional, Tuple

from .sql_dialect import SQLDialect

# Compiled regex patterns for performance
_RE_COMMENTS_SINGLE = re.compile(r"--.*$", re.MULTILINE)
_RE_COMMENTS_MULTI = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_ODBC_CURDATE = re.compile(r"\{fn\s+CURDATE\s*\(\s*\)\s*\}", re.IGNORECASE)
_RE_ODBC_NOW = re.compile(r"\{fn\s+NOW\s*\(\s*\)\s*\}", re.IGNORECASE)
_RE_ODBC_CURRENT_DATE = re.compile(r"\{fn\s+CURRENT_DATE\s*\(\s*\)\s*\}", re.IGNORECASE)
_RE_ODBC_CURRENT_TIME = re.compile(r"\{fn\s+CURRENT_TIME\s*\(\s*\)\s*\}", re.IGNORECASE)
_RE_ODBC_CURRENT_TIMESTAMP = re.compile(r"\{fn\s+CURRENT_TIMESTAMP\s*\(\s*\)\s*\}", re.IGNORECASE)
_RE_ODBC_GENERIC = re.compile(r"\{fn\s+[^}]*\}", re.IGNORECASE)
_RE_STAR_SELECT = re.compile(r"(\bSELECT\b)(\s+)\*", re.IGNORECASE)
_RE_STAR_COMMA = re.compile(r",\s*\*\s*,")
_RE_STAR_FROM = re.compile(r"\*\s+(\bFROM\b)", re.IGNORECASE)
_RE_TO_DATE_VAR = re.compile(r"\bto_date\s*\(\s*@\w+\([^)]*\)\s*,\s*'([^']+)'\s*\)", re.IGNORECASE)
_RE_TO_DATE_TWO = re.compile(r"\bto_date\s*\(\s*([^()]*(?:\([^()]*\)[^()]*)*)\s*,\s*'([^']+)'\s*\)", re.IGNORECASE)
_RE_TO_DATE_ONE = re.compile(r"\bto_date\s*\(\s*([^()]*(?:\([^()]*\)[^()]*)*)\s*\)", re.IGNORECASE)
_RE_VAR_FUNC = re.compile(r"@\w+\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_TRAILING_PAREN = re.compile(r"\s+\)")
_RE_LEADING_QUOTE = re.compile(r'^"')


class SQLPreprocessor:
    """Preprocessor for SQL statements."""

    def __init__(self, dialect: SQLDialect = SQLDialect.ORACLE):
        """
        Initialize SQL preprocessor.

        Args:
            dialect: SQL dialect to use for preprocessing (default: ORACLE).
        """
        self.dialect = dialect
        self.procedures: Dict[str, Dict[str, str]] = {}
        self.table_functions: Dict[str, str] = {}

    def preprocess(self, sql: str) -> str:
        """
        Clean and normalize SQL statement.

        Performs the following steps:
        - Remove comments (single‑line `--` and multi‑line `/* */`)
        - Remove Oracle hints
        - Remove outer join syntax (+)
        - Remove T-SQL GO separator
        - Strip PL/SQL blocks
        - Replace TABLE() functions
        - Replace ODBC {fn ...} functions
        - Replace CONVERT functions with CAST
        - Replace variable functions (e.g., @func()) with empty string
        - Replace TO_DATE functions with CAST('2000-01-01' AS DATE)
        - Handle star operator (`*`) to avoid parsing errors
        - Normalize identifier quoting (square brackets to dialect‑appropriate quotes)
        - Fix unbalanced parentheses
        - Fix common whitespace and punctuation issues

        Args:
            sql: Raw SQL string.

        Returns:
            Preprocessed SQL string ready for parsing.
        """
        if not sql:
            return sql

        # Paren balance logging
        def _bal(s):
            return s.count('('), s.count(')'), s.count('(') - s.count(')')

        initial = _bal(sql)
        prev_diff = initial[2]

        steps = [
            ("remove_comments", self._remove_comments),
            ("remove_oracle_hints", self._remove_oracle_hints),
            ("remove_outer_join", self._remove_outer_join),
            ("remove_go_separator", self._remove_go_separator),
            ("strip_plsql_block", self._strip_plsql_block),
            ("replace_procedure_syntax", self._replace_procedure_syntax),
            ("replace_table_function", self._replace_table_function),
            ("replace_odbc_functions", self._replace_odbc_functions),
            ("replace_convert_functions", self._replace_convert_functions),
            ("replace_variable_functions", self._replace_variable_functions),
            ("replace_to_date_functions", self._replace_to_date_functions),
            ("handle_star_operator", self._handle_star_operator),
            ("remove_square_brackets", self._remove_square_brackets),
            ("fix_case_expressions", self._fix_case_expressions),
            ("fix_between_expressions", self._fix_between_expressions),
            ("fix_truncated_expressions", self._fix_truncated_expressions),
            ("fix_cte_issues", self._fix_cte_issues),
            ("fix_if_expressions", self._fix_if_expressions),
            ("fix_empty_parens", self._fix_empty_parens),
            ("fix_extra_close_paren", self._fix_extra_close_paren),
            ("fix_parens", self._fix_parens),
            ("fix_common_issues", self._fix_common_issues),
        ]

        for step_name, step_fn in steps:
            sql = step_fn(sql)
            diff = sql.count('(') - sql.count(')')
            if diff != prev_diff:
                prev_diff = diff

        final = _bal(sql)
        return sql

    def preprocess_stepwise(self, sql: str) -> Generator[Tuple[str, str], None, None]:
        """
        Yield (step_name, sql_after_step) for each cleaning step.

        Each step receives the output of the previous step, so transformations
        accumulate. The caller can try parsing after each step and stop as
        soon as parsing succeeds.

        Yields:
            Tuples of (step_name, sql_after_this_step).
        """
        if not sql:
            return

        steps = [
            ("remove_comments", self._remove_comments),
            ("remove_oracle_hints", self._remove_oracle_hints),
            ("remove_outer_join", self._remove_outer_join),
            ("remove_go_separator", self._remove_go_separator),
            ("strip_plsql_block", self._strip_plsql_block),
            ("replace_procedure_syntax", self._replace_procedure_syntax),
            ("replace_table_function", self._replace_table_function),
            ("replace_odbc_functions", self._replace_odbc_functions),
            ("replace_convert_functions", self._replace_convert_functions),
            ("replace_variable_functions", self._replace_variable_functions),
            ("replace_to_date_functions", self._replace_to_date_functions),
            ("handle_star_operator", self._handle_star_operator),
            ("remove_square_brackets", self._remove_square_brackets),
            ("fix_case_expressions", self._fix_case_expressions),
            ("fix_between_expressions", self._fix_between_expressions),
            ("fix_truncated_expressions", self._fix_truncated_expressions),
            ("fix_cte_issues", self._fix_cte_issues),
            ("fix_if_expressions", self._fix_if_expressions),
            ("fix_empty_parens", self._fix_empty_parens),
            ("fix_extra_close_paren", self._fix_extra_close_paren),
            ("fix_parens", self._fix_parens),
            ("fix_common_issues", self._fix_common_issues),
        ]

        prev_diff = sql.count('(') - sql.count(')')
        for step_name, step_fn in steps:
            sql = step_fn(sql)
            diff = sql.count('(') - sql.count(')')
            if diff != prev_diff:
                prev_diff = diff
            yield step_name, sql

    def _remove_comments(self, sql: str) -> str:
        """Removes -- and /* */ comments, skipping those inside string literals.

        Handles: \\n, \\r\\n, end-of-line as -- comment terminator.
        """
        result = []
        i = 0
        n = len(sql)
        in_string = False
        while i < n:
            ch = sql[i]
            if in_string:
                result.append(ch)
                if ch == '\\' and i + 1 < n:
                    result.append(sql[i + 1])
                    i += 2
                    continue
                if ch == "'" and i + 1 < n and sql[i + 1] == "'":
                    result.append(sql[i + 1])
                    i += 2
                    continue
                if ch == "'":
                    in_string = False
                i += 1
                continue
            if ch == "'":
                in_string = True
                result.append(ch)
                i += 1
                continue
            if ch == '-' and i + 1 < n and sql[i + 1] == '-':
                # -- comment: skip to \r, \n or end of line
                while i < n and sql[i] not in ('\r', '\n'):
                    i += 1
                continue
            if ch == '/' and i + 1 < n and sql[i + 1] == '*':
                i += 2
                # /* comment: skip to */ or end of string
                while i < n - 1 and not (sql[i] == '*' and sql[i + 1] == '/'):
                    i += 1
                i += 2
                continue
            result.append(ch)
            i += 1
        return ''.join(result).strip()

    def _remove_oracle_hints(self, sql: str) -> str:
        """Removes Oracle hints: /*+ ... */."""
        return re.sub(r'/\*\+.*?\*/', '', sql, flags=re.DOTALL)

    def _remove_outer_join(self, sql: str) -> str:
        """Removes outer join syntax (+)."""
        return re.sub(r'\(\s*\+\s*\)', '', sql)

    def _remove_go_separator(self, sql: str) -> str:
        """Removes T-SQL batch separator GO."""
        return re.sub(r'\bGO\b', '', sql, flags=re.IGNORECASE)

    def _strip_plsql_block(self, sql: str) -> str:
        """Strips PL/SQL blocks (CREATE FUNCTION, BEGIN...END etc).

        If SQL already starts with WITH or SELECT — leaves it untouched.
        Otherwise looks for end of PL/SQL (END; or / on its own line)
        and returns everything after it.
        """
        first_word = sql.strip().split()[0].upper() if sql.strip() else ''
        if first_word in ('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE', 'MERGE'):
            return sql

        # Look for END; (and optional / after it) — PL/SQL end marker
        match = re.search(r'\bEND\s*;\s*\n?\s*/?\s*$', sql, re.IGNORECASE | re.MULTILINE)
        if match:
            return sql[match.end():].strip()

        # Look for / on its own line — alternative PL/SQL end marker
        match = re.search(r'^\s*/\s*$', sql, re.MULTILINE)
        if match:
            return sql[match.end():].strip()

        return sql

    def _replace_table_function(self, sql: str) -> str:
        """Replaces TABLE(func_name(...)) with func_name.

        Uses bracket matching for nested arguments.
        Function name is stored in self.table_functions.
        """
        result = []
        i = 0
        while i < len(sql):
            upper = sql[i:].upper()
            if upper.startswith('TABLE') and (i == 0 or not sql[i-1].isalnum()):
                j = i + 5
                while j < len(sql) and sql[j] in ' \t\n\r':
                    j += 1
                if j < len(sql) and sql[j] == '(':
                    # Find matching closing bracket
                    depth = 1
                    k = j + 1
                    while k < len(sql) and depth > 0:
                        if sql[k] == '(':
                            depth += 1
                        elif sql[k] == ')':
                            depth -= 1
                        k += 1
                    # Extract function name from inner content
                    inner = sql[j+1:k-1].strip()
                    m = re.match(r'(\w+)\s*\(', inner)
                    if m:
                        func_name = m.group(1)
                        self.table_functions[func_name] = "Функция"
                        result.append(func_name)
                        i = k
                        continue
            result.append(sql[i])
            i += 1
        return ''.join(result)

    def _replace_procedure_syntax(self, sql: str) -> str:
        """Replace <Procedure ...>...</Procedure> XML-like blocks with synthetic table references.

        Extracts qualifier, owner, name attributes and stores them in self.procedures
        keyed by the synthetic table name. The replacement is schema.table_name so
        sqlglot can parse it as a normal table.
        """
        pattern = (
            r"<Procedure\s+"
            r'(?:uid="[^"]*"\s+)?'  # optional uid
            r'(?:qualifier="([^"]*)"\s+)?'
            r'(?:owner="([^"]*)"\s+)?'
            r'name="([^"]*)"\s+'
            r'type="([^"]*)"'
            r".*?"
            r"</Procedure>"
        )

        def _replace_proc(match: re.Match) -> str:
            qualifier = match.group(1) or ""
            owner = match.group(2) or ""
            name = match.group(3) or ""
            proc_type = match.group(4) or ""

            schema_parts = [p for p in [qualifier, owner] if p]
            schema = ".".join(schema_parts)

            # Synthetic table reference: schema."name"
            if schema:
                ref = f'{schema}."{name}"'
            else:
                ref = f'"{name}"'

            self.procedures[ref] = {
                "qualifier": qualifier,
                "owner": owner,
                "name": name,
                "type": proc_type,
            }
            return ref

        sql = re.sub(pattern, _replace_proc, sql, flags=re.DOTALL | re.IGNORECASE)
        return sql

    def _replace_odbc_functions(self, sql: str) -> str:
        """Replaces ODBC {fn ...} syntax with standard SQL functions."""
        sql = _RE_ODBC_CURDATE.sub("CURRENT_DATE", sql)
        sql = _RE_ODBC_NOW.sub("CURRENT_TIMESTAMP", sql)
        sql = _RE_ODBC_CURRENT_DATE.sub("CURRENT_DATE", sql)
        sql = _RE_ODBC_CURRENT_TIME.sub("CURRENT_TIME", sql)
        sql = _RE_ODBC_CURRENT_TIMESTAMP.sub("CURRENT_TIMESTAMP", sql)
        sql = _RE_ODBC_GENERIC.sub("''", sql)
        return sql

    def _apply_patterns(self, sql: str, patterns: list[tuple[str, str]]) -> str:
        """Apply multiple regex substitutions sequentially."""
        result = sql
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _replace_convert_functions(self, sql: str) -> str:
        # [^,)]+ stops at commas and closing parens for the base expression
        # (?:\([^)]*\)[^,)]*)* allows balanced nested parens like GETDATE()
        _expr = r"([^,)]+(?:\([^)]*\)[^,)]*)*)"
        convert_patterns = [
            (rf"\bCONVERT\s*\(\s*datetime\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime)"),
            (rf"\bCONVERT\s*\(\s*date\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS date)"),
            (rf"\bCONVERT\s*\(\s*smalldatetime\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS smalldatetime)"),
            (rf"\bCONVERT\s*\(\s*datetime2\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)", r"CAST(\1 AS datetime2)"),
            (
                rf"\bCONVERT\s*\(\s*(numeric|decimal)\s*\(\s*\d+\s*,\s*\d+\s*\)\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)",
                r"CAST(\2 AS \1)",
            ),
            (
                rf"\bCONVERT\s*\(\s*(var)?char\s*\(\s*\d+\s*\)\s*,\s*{_expr}\s*(?:,\s*\d+\s*)?\)",
                r"CAST(\2 AS \1char)",
            ),
            (rf"\bCONVERT\s*\(\s*(\w+)\s*,\s*{_expr}\s*\)", r"CAST(\2 AS \1)"),
        ]
        return self._apply_patterns(sql, convert_patterns)

    def _replace_to_date_functions(self, sql: str) -> str:
        sql = _RE_TO_DATE_VAR.sub("CAST('2000-01-01' AS DATE)", sql)
        sql = _RE_TO_DATE_TWO.sub("CAST('2000-01-01' AS DATE)", sql)
        sql = _RE_TO_DATE_ONE.sub("CAST('2000-01-01' AS DATE)", sql)
        return sql

    def _replace_variable_functions(self, sql: str) -> str:
        return _RE_VAR_FUNC.sub("''", sql)

    def _handle_star_operator(self, sql: str) -> str:
        sql = _RE_STAR_SELECT.sub(r"\1 _star_", sql)
        sql = sql.replace(".*", "._star_")
        sql = _RE_STAR_COMMA.sub(",_star_,", sql)
        sql = _RE_STAR_FROM.sub(r"_star_ \1", sql)
        return sql

    def _remove_square_brackets(self, sql: str) -> str:
        """
        Replace square brackets outside string literals with appropriate quoting.
        For T-SQL keep brackets, for MySQL use backticks, for others double quotes.
        """
        # States: 0 - outside quotes, 1 - inside single quotes, 2 - inside double quotes
        state = 0
        result = []
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "'" and state == 0:
                state = 1
                result.append(ch)
            elif ch == "'" and state == 1:
                # Check escaping: next quote?
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
                # Found opening bracket outside quotes
                # Look for closing bracket
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
                    i = j  # skip closing bracket
                else:
                    # no closing bracket, leave as is
                    result.append(ch)
            elif ch == ']' and state == 0:
                # Closing bracket outside quotes without opening? leave as is
                result.append(ch)
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    def _fix_case_expressions(self, sql: str) -> str:
        """Fixes unclosed CASE expressions.

        Counts CASE and END occurrences (outside string literals).
        If CASE count > END count — inserts missing END before clause keywords
        (FROM, WHERE, GROUP BY, ORDER BY, HAVING, UNION etc.) or at end of query.
        """

        def _is_word_char(c: str) -> bool:
            return c.isalnum() or c == '_'

        case_positions = []
        end_positions = []
        in_string = False
        escape = False
        i = 0
        sql_upper = sql.upper()
        len_sql = len(sql)

        while i < len_sql:
            ch = sql[i]
            if escape:
                escape = False
                i += 1
                continue
            if ch == '\\':
                escape = True
                i += 1
                continue
            if ch == "'":
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue

            # Check CASE (as whole word)
            if sql_upper[i:i + 4] == 'CASE':
                before_ok = (i == 0 or not _is_word_char(sql_upper[i - 1]))
                after_ok = (i + 4 >= len_sql or not _is_word_char(sql_upper[i + 4]))
                if before_ok and after_ok:
                    case_positions.append(i)

            # Check END (as whole word)
            if sql_upper[i:i + 3] == 'END':
                before_ok = (i == 0 or not _is_word_char(sql_upper[i - 1]))
                after_ch = sql_upper[i + 3] if i + 3 < len_sql else ' '
                after_ok = not _is_word_char(after_ch)
                if before_ok and after_ok:
                    end_positions.append(i)

            i += 1

        diff = len(case_positions) - len(end_positions)
        if diff <= 0:
            return sql

        # Clause keywords before which END should be inserted
        clause_re = re.compile(
            r'\b(FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|UNION|INTERSECT|EXCEPT|LIMIT|FETCH)\b',
            re.IGNORECASE,
        )

        # Find clause positions outside strings
        clause_positions = []
        for m in clause_re.finditer(sql):
            pos = m.start()
            # Check that position is outside string literal
            in_str = False
            esc = False
            for j in range(pos):
                c = sql[j]
                if esc:
                    esc = False
                    continue
                if c == '\\':
                    esc = True
                    continue
                if c == "'":
                    in_str = not in_str
            if not in_str:
                clause_positions.append((pos, m.group()))

        # Insert END before clauses
        result = sql
        inserted = 0
        for pos, _clause in clause_positions:
            if inserted >= diff:
                break
            result = result[:pos] + 'END ' + result[pos:]
            inserted += 1

        # If still unclosed CASE — add END at end
        remaining = diff - inserted
        for _ in range(remaining):
            if result.rstrip().endswith(';'):
                result = result.rstrip()[:-1] + ' END;'
            else:
                result = result.rstrip() + ' END'

        return result

    def _fix_between_expressions(self, sql: str) -> str:
        """Fixes incomplete BETWEEN expressions.

        If BETWEEN doesn't have the full "low AND high" construct —
        adds missing operands with a placeholder value.
        """

        def _is_word_char(c: str) -> bool:
            return c.isalnum() or c == '_'

        def _skip_string(pos: int) -> int:
            i = pos + 1
            while i < len(sql):
                if sql[i] == '\\':
                    i += 2
                    continue
                if sql[i] == "'":
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        i += 2
                        continue
                    return i + 1
                i += 1
            return i

        def _read_expr(start: int) -> int:
            """Reads an expression, returns position right after it."""
            i = start
            depth = 0
            while i < len(sql):
                c = sql[i]
                if c == '(':
                    depth += 1
                elif c == ')':
                    if depth > 0:
                        depth -= 1
                    else:
                        return i
                elif c == "'":
                    i = _skip_string(i)
                    continue
                elif depth == 0:
                    if c.upper() in ('A', 'O'):
                        rest = sql_upper[i:]
                        for kw in ('AND ', 'AND\t', 'AND\n', 'AND;',
                                   'AND,', 'AND)', 'AND<', 'AND>',
                                   'OR ', 'OR\t', 'OR\n', 'OR;',
                                   'OR,', 'OR)', 'OR<', 'OR>'):
                            if rest.startswith(kw):
                                return i
                        if rest in ('AND', 'OR'):
                            return i
                    elif c == ',' or c in ('<', '>', '=', '!', '|', '&'):
                        return i
                i += 1
            return i

        def _fix_between_keyword(keyword_len: int) -> None:
            """Handles BETWEEN or NOT BETWEEN."""
            nonlocal i
            result.append(sql[i:i + keyword_len])
            i += keyword_len

            # Spaces after keyword
            while i < len_sql and sql[i] in ' \t\n\r':
                result.append(sql[i])
                i += 1

            # Read low
            low_end = _read_expr(i)
            low_val = sql[i:low_end].strip()
            result.append(sql[i:low_end])
            i = low_end

            # Check AND + high
            rest = sql_upper[i:].lstrip()
            spaces = len(sql[i:]) - len(sql[i:].lstrip())
            and_start = i + spaces

            if rest.startswith('AND'):
                after_and = sql_upper[and_start + 3:].lstrip() if and_start + 3 < len_sql else ''
                has_high = (after_and and after_and[0] not in
                           (';', ',', ')', 'O', 'W', 'G', 'H', 'U', 'L', 'F'))
                if has_high:
                    # AND + high present — leave as is
                    pass
                else:
                    # AND present but no high — skip old AND, put our own
                    result.append(sql[i:and_start])
                    result.append(' AND ')
                    result.append(low_val or '1')
                    i = and_start + 3
            elif low_val:
                # No AND — add it
                result.append(' AND ')
                result.append(low_val)

        result = []
        i = 0
        sql_upper = sql.upper()
        len_sql = len(sql)
        in_string = False
        escape = False

        while i < len_sql:
            ch = sql[i]
            if escape:
                escape = False
                result.append(ch)
                i += 1
                continue
            if ch == '\\':
                escape = True
                result.append(ch)
                i += 1
                continue
            if ch == "'":
                in_string = not in_string
                result.append(ch)
                i += 1
                continue
            if in_string:
                result.append(ch)
                i += 1
                continue

            # NOT BETWEEN
            if sql_upper[i:i + 12] == 'NOT BETWEEN':
                before_ok = (i == 0 or not _is_word_char(sql_upper[i - 1]))
                after_ch = sql_upper[i + 12] if i + 12 < len_sql else ' '
                if before_ok and not _is_word_char(after_ch):
                    _fix_between_keyword(12)
                    continue

            # BETWEEN
            if sql_upper[i:i + 7] == 'BETWEEN':
                before_ok = (i == 0 or not _is_word_char(sql_upper[i - 1]))
                after_ch = sql_upper[i + 7] if i + 7 < len_sql else ' '
                if before_ok and not _is_word_char(after_ch):
                    _fix_between_keyword(7)
                    continue

            result.append(ch)
            i += 1

        return ''.join(result)

    def _fix_truncated_expressions(self, sql: str) -> str:
        """Fixes truncated expressions (operator arguments).

        Handles:
          x IS              -> x IS NULL
          x IS NOT          -> x IS NOT NULL
          x LIKE            -> x LIKE ''
          x >, x <, ...     -> x > 0
          x =               -> x = 0
          x +, x -, x *, x / -> x + 0
        """
        # IS NOT without value (BEFORE other IS rules!)
        sql = re.sub(
            r'\bIS\s+NOT\s*$', 'IS NOT NULL', sql, flags=re.IGNORECASE
        )
        # IS NOT before another keyword (AND/OR/WHERE/...)
        sql = re.sub(
            r'\bIS\s+NOT\s+(?=AND\b|OR\b|WHERE\b|GROUP\b|HAVING\b|ORDER\b|LIMIT\b|;|$)',
            'IS NOT NULL ', sql, flags=re.IGNORECASE
        )
        # IS without NULL/TRUE/FALSE (only IS, not IS NOT)
        sql = re.sub(
            r'\bIS\s+(?!NULL\b|TRUE\b|FALSE\b|NOT\b)', 'IS NULL ', sql, flags=re.IGNORECASE
        )
        # IS at end of string
        sql = re.sub(
            r'\bIS\s*$', 'IS NULL', sql, flags=re.IGNORECASE
        )
        # LIKE without pattern
        sql = re.sub(
            r'\bLIKE\s*$', "LIKE ''", sql, flags=re.IGNORECASE
        )
        # Comparison operators without right operand
        for op in ('>=', '<=', '<>', '!=', '>', '<', '='):
            # Operator at end of string or before ; or )
            sql = re.sub(
                rf'\b\w+\s*{re.escape(op)}\s*$', rf'\g<0> 0', sql, flags=re.IGNORECASE
            )
            # Operator before AND/OR/WHERE/GROUP/HAVING/ORDER/LIMIT
            sql = re.sub(
                rf'(\b\w+\s*{re.escape(op)})\s+(?=AND\b|OR\b|WHERE\b|GROUP\b|HAVING\b|ORDER\b|LIMIT\b)',
                r'\1 0 ', sql, flags=re.IGNORECASE
            )
        # Arithmetic operators without right operand (x +, x -, x *, x /)
        for op in ('+', '-', '*', '/'):
            sql = re.sub(
                rf'(\b\w+)\s*{re.escape(op)}\s*$', rf'\1 {op} 0', sql, flags=re.IGNORECASE
            )
        return sql

    def _fix_if_expressions(self, sql: str) -> str:
        """Converts IF(condition, true_val, false_val) to CASE WHEN.

        IF() is a MySQL/DB2 function not supported in many dialects.
        Replaces with standard CASE WHEN ... THEN ... ELSE ... END.
        Handles nested IF by replacing inner ones first.
        """
        def _replace_if(s: str) -> str:
            idx = 0
            while idx < len(s):
                # Find IF(
                match = re.search(r'\bIF\s*\(', s[idx:], re.IGNORECASE)
                if not match:
                    break
                start = idx + match.start()
                paren_start = idx + match.end() - 1  # position of (
                # Balance brackets
                depth = 1
                i = paren_start + 1
                while i < len(s) and depth > 0:
                    if s[i] == '(':
                        depth += 1
                    elif s[i] == ')':
                        depth -= 1
                    i += 1
                if depth != 0:
                    idx = paren_start + 1
                    continue
                # i now points to ) closing IF
                inner = s[paren_start + 1:i - 1]
                # Split inner by commas at depth 0
                args = []
                current = []
                d = 0
                in_str = False
                for ch in inner:
                    if ch == "'" and (len(current) == 0 or current[-1] != '\\'):
                        in_str = not in_str
                    if not in_str:
                        if ch == '(':
                            d += 1
                        elif ch == ')':
                            d -= 1
                        elif ch == ',' and d == 0:
                            args.append(''.join(current).strip())
                            current = []
                            continue
                    current.append(ch)
                args.append(''.join(current).strip())
                if len(args) == 3:
                    replacement = f"CASE WHEN {args[0]} THEN {args[1]} ELSE {args[2]} END"
                elif len(args) == 2:
                    replacement = f"CASE WHEN {args[0]} THEN {args[1]} END"
                else:
                    idx = paren_start + 1
                    continue
                s = s[:start] + replacement + s[i:]
                idx = start + len(replacement)
            return s

        # Repeat while IF( exists
        prev = None
        while prev != sql:
            prev = sql
            sql = _replace_if(sql)
        return sql

    def _fix_empty_parens(self, sql: str) -> str:
        """Removes empty parentheses () after table/function names."""
        sql = re.sub(r'(\w+)\s*\(\s*\)', r'\1', sql)
        return sql

    def _fix_cte_issues(self, sql: str) -> str:
        """Fixes typical CTE (WITH ... AS) issues.

        - WITH ... AS () SELECT -> WITH ... AS (SELECT ...)
        - Removes trailing ; before WITH
        """
        # WITH ... AS () SELECT -> WITH ... AS (SELECT ...)
        sql = re.sub(
            r'\bWITH\b\s+(\w+)\s+\bAS\s*\(\s*\)\s*(\bSELECT\b)',
            r'WITH \1 AS (SELECT * FROM dual) \2',
            sql, flags=re.IGNORECASE
        )
        # Remove ; before WITH (shouldn't break CTE)
        sql = re.sub(r';\s*\bWITH\b', ' WITH', sql, flags=re.IGNORECASE)
        return sql

    def _fix_extra_close_paren(self, sql: str) -> str:
        """Removes extra ) and AS after subquery aliases.

        sqlglot Oracle doesn't support AS for table aliases in FROM.
        """
        # ) alias ) AS , -> ) alias ,
        sql = re.sub(r'\)\s+(\w+)\s*\)\s+AS\s*,', r') \1,', sql, flags=re.IGNORECASE)
        # ) alias ) , -> ) alias ,
        sql = re.sub(r'\)\s+(\w+)\s*\)\s*,', r') \1,', sql)
        # ) alias ) AS WHERE -> ) alias WHERE
        sql = re.sub(r'\)\s+(\w+)\s*\)\s+AS\s+WHERE', r') \1 WHERE', sql, flags=re.IGNORECASE)
        # ) alias ) WHERE -> ) alias WHERE
        sql = re.sub(r'\)\s+(\w+)\s*\)\s+WHERE', r') \1 WHERE', sql)
        # ) alias AS , -> ) alias ,
        sql = re.sub(r'\)\s+(\w+)\s+AS\s*,', r') \1,', sql, flags=re.IGNORECASE)
        # ) alias AS WHERE -> ) alias WHERE
        sql = re.sub(r'\)\s+(\w+)\s+AS\s+WHERE', r') \1 WHERE', sql, flags=re.IGNORECASE)
        # Replace 'as.' (only as table alias) with '_asa_.'
        sql = re.sub(r'(?<!\w)as\.', '_asa_.', sql)
        return sql

    def _fix_parens(self, sql: str) -> str:
        """Fixes unbalanced parentheses.

        Handles two cases:
        1. More `(` than `)` — inserts missing `)` before clauses or at end.
        2. More `)` than `(` — removes extra `)` at end or before clauses.
        """
        _CLAUSE_KW = re.compile(
            r'\b(FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|UNION|INTERSECT|EXCEPT|LIMIT|FETCH|THEN|ELSE|END|;)\b',
            re.IGNORECASE,
        )

        def _is_word_char(c: str) -> bool:
            return c.isalnum() or c == '_'

        # Count parens outside strings
        open_count = 0
        close_count = 0
        in_string = False
        escape = False
        for ch in sql:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == "'":
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '(':
                open_count += 1
            elif ch == ')':
                close_count += 1

        # Balanced — nothing to do
        if open_count == close_count:
            return sql

        diff = open_count - close_count

        if diff > 0:
            # More `(` — insert `)` before clauses
            result = []
            i = 0
            len_sql = len(sql)
            in_string = False
            escape = False
            depth = 0
            inserts = []

            while i < len_sql:
                ch = sql[i]
                if escape:
                    escape = False
                    i += 1
                    continue
                if ch == '\\':
                    escape = True
                    i += 1
                    continue
                if ch == "'":
                    in_string = not in_string
                    i += 1
                    continue
                if in_string:
                    i += 1
                    continue
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    if depth > 0:
                        depth -= 1

                if depth > 0:
                    rest = sql[i:]
                    m = _CLAUSE_KW.match(rest)
                    if m:
                        inserts.append((i, depth))
                        depth = 0

                i += 1

            if inserts:
                last = 0
                for pos, count in inserts:
                    result.append(sql[last:pos])
                    result.append(')' * count + ' ')
                    last = pos
                result.append(sql[last:])
                sql = ''.join(result)

            # If still unclosed — add at end
            open_count2 = sum(1 for ch in sql if ch == '(')
            close_count2 = sum(1 for ch in sql if ch == ')')
            remaining = open_count2 - close_count2
            if remaining > 0:
                if sql.rstrip().endswith(';'):
                    sql = sql.rstrip()[:-1] + ')' * remaining + ';'
                else:
                    sql = sql.rstrip() + ')' * remaining

        elif diff < 0:
            # More `)` — remove extra `)` where depth goes < 0
            to_remove = -diff
            result = list(sql)
            in_string = False
            escape = False
            depth = 0
            removed = 0
            for idx in range(len(sql)):
                ch = sql[idx]
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == "'":
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    if depth > 0:
                        depth -= 1
                    elif removed < to_remove:
                        # Extra ) — remove
                        result[idx] = ''
                        removed += 1
            sql = ''.join(result)

        return sql

    def _fix_common_issues(self, sql: str) -> str:
        sql = _RE_WHITESPACE.sub(" ", sql)
        sql = sql.replace(", ,", ",")
        sql = sql.replace(",.", ",")
        sql = _RE_LEADING_QUOTE.sub("", sql)
        sql = _RE_TRAILING_PAREN.sub(")", sql)
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
