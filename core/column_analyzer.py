"""
Detailed column analyzer for SQL AST.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sqlglot import exp

from models.sql_metadata import ColumnMetadata, TableInfo, TableType


CALCULATION_NODES = (
    exp.AggFunc,
    exp.Anonymous,
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
    exp.Mod,
    exp.Case,
    exp.Cast,
    exp.Window,
)


@dataclass
class ScopeInfo:
    """Represents the table‑alias mapping within a single SELECT scope."""

    alias_to_table: Dict[str, str]
    tables: Set[str]


class DetailedColumnAnalyzer:
    """Detailed analyzer for columns, aliases and usage contexts."""

    def __init__(self, ast: exp.Expression):
        """
        Initialize analyzer with a sqlglot AST.

        Args:
            ast: Root node of the sqlglot AST (usually a Select expression).
        """
        self.ast = ast
        self.columns: Dict[str, ColumnMetadata] = {}
        self.tables: Dict[Tuple[Optional[str], str, TableType], TableInfo] = {}
        self.column_alias_to_source: Dict[str, str] = {}
        self.scope_by_select_id: Dict[int, ScopeInfo] = {}
        self.subquery_column_map: Dict[Tuple[str, str], str] = {}
        self.cte_column_map: Dict[Tuple[str, str], str] = {}
        self.source_alias_hints: Dict[str, Set[str]] = {}
        self.select_aliases: Set[str] = set()

    def analyze(self) -> Tuple[List[ColumnMetadata], List[TableInfo], str]:
        """
        Perform full analysis of the AST.

        Steps:
        1. Collect tables (CTEs, base tables, subqueries)
        2. Build alias‑to‑table mapping per SELECT scope
        3. Map column names in subqueries and CTEs to their source columns
        4. Scan all nodes once, processing aliases and columns
        5. Handle JOIN USING clauses
        6. Apply source‑alias hints (columns exposed through subquery/CTE aliases)
        7. Normalize column metadata

        Returns:
            Tuple of (list of columns, list of tables, formatted text sample).
        """
        self._collect_tables()
        self._collect_scopes()
        self._collect_subquery_and_cte_column_maps()
        self._scan_nodes_once()
        self._process_join_using()
        self._apply_source_alias_hints()
        columns = list(self.columns.values())
        for column in columns:
            column.normalize()
        return columns, list(self.tables.values()), self._render_columns_sample(columns)

    def _collect_tables(self) -> None:
        for cte in self.ast.find_all(exp.CTE):
            cte_name = cte.alias_or_name
            if cte_name:
                self._upsert_table(cte_name, None, cte_name, TableType.CTE)

        for table in self.ast.find_all(exp.Table):
            name = table.name
            schema = table.db
            alias = table.alias_or_name if table.alias else None
            table_type = TableType.CTE if self._is_cte_table(name) else TableType.TABLE
            self._upsert_table(name, schema, alias, table_type)

        for subquery in self.ast.find_all(exp.Subquery):
            alias = subquery.alias_or_name
            if alias:
                self._upsert_table(alias, None, alias, TableType.SUBQUERY)

    def _collect_scopes(self) -> None:
        for select in self.ast.find_all(exp.Select):
            alias_to_table: Dict[str, str] = {}
            tables: Set[str] = set()

            from_node = select.args.get("from_")
            if from_node:
                for table in from_node.find_all(exp.Table):
                    name = table.name
                    alias = table.alias_or_name if table.alias else None
                    tables.add(name)
                    if alias:
                        alias_to_table[alias] = name

            joins = select.args.get("joins") or []
            for join in joins:
                for table in join.find_all(exp.Table):
                    name = table.name
                    alias = table.alias_or_name if table.alias else None
                    tables.add(name)
                    if alias:
                        alias_to_table[alias] = name

            self.scope_by_select_id[id(select)] = ScopeInfo(alias_to_table=alias_to_table, tables=tables)

    def _scan_nodes_once(self) -> None:
        for node in self.ast.walk():
            if isinstance(node, exp.Alias):
                self._process_alias(node)
                continue

            if isinstance(node, exp.Column):
                self._process_column(node)

    def _process_alias(self, alias_node: exp.Alias) -> None:
        alias_name = alias_node.alias_or_name
        if not alias_name:
            return
        self.select_aliases.add(alias_name)

        source_columns = list(alias_node.this.find_all(exp.Column))
        if not source_columns:
            return

        alias_is_calculation = self._expression_is_calculation(alias_node.this)

        for src in source_columns:
            source_key, source_table_alias = self._resolve_column_key(src)
            if not source_key:
                continue

            meta = self._get_or_create_column(source_key, source_table_alias)
            if alias_name not in meta.column_aliases:
                meta.column_aliases.append(alias_name)
            if alias_name not in meta.aliases:
                meta.aliases.append(alias_name)

            # Map ORDER BY alias -> source only for direct/non-calculated aliases (e.g. u.id AS user_id).
            if not alias_is_calculation:
                self.column_alias_to_source.setdefault(alias_name, source_key)

            calc, calc_parent = self._is_calculation_column(src)
            if calc:
                meta.is_calculation = True
                meta.calculation_type = self._calculation_type(calc_parent)
                meta.calculation_expression = calc_parent.sql() if calc_parent else alias_node.this.sql()

    def _process_column(self, column_node: exp.Column) -> None:
        key, table_alias = self._resolve_column_key(column_node)
        if not key:
            return

        meta = self._get_or_create_column(key, table_alias)
        if table_alias and table_alias != meta.table:
            alias_ref = f"{table_alias}.{meta.column_name}"
            if alias_ref not in meta.aliases:
                meta.aliases.append(alias_ref)

        for context in self._detect_usage_context(column_node):
            meta.usage_locations.append(context)

        calc, calc_parent = self._is_calculation_column(column_node)
        if calc:
            meta.is_calculation = True
            meta.calculation_type = self._calculation_type(calc_parent)
            meta.calculation_expression = calc_parent.sql() if calc_parent else column_node.sql()

        meta.usage_count += 1

        # Также обновить колонку CTE, если ссылка идет через алиас CTE
        if table_alias and self._is_cte_table(table_alias):
            col_name = column_node.name
            if col_name and col_name != "_star_":
                cte_key = f"{table_alias}.{col_name}"
                cte_meta = self.columns.get(cte_key)
                if cte_meta and cte_meta is not meta:  # если это не та же самая мета
                    cte_meta.usage_count += 1
                    for context in self._detect_usage_context(column_node):
                        if context not in cte_meta.usage_locations:
                            cte_meta.usage_locations.append(context)

    def _process_join_using(self) -> None:
        for join in self.ast.find_all(exp.Join):
            using_args = join.args.get("using")
            if not using_args:
                continue

            names: List[str] = []
            for expr_item in using_args:
                if isinstance(expr_item, exp.Identifier):
                    names.append(expr_item.name)
                elif hasattr(expr_item, "name"):
                    names.append(expr_item.name)

            if not names:
                continue

            select_scope = self._nearest_select_scope(join)
            if not select_scope:
                continue

            candidate_tables = sorted(select_scope.tables)
            for col_name in names:
                for table_name in candidate_tables:
                    key = f"{table_name}.{col_name}"
                    meta = self._get_or_create_column(key, None)
                    meta.usage_locations.append("JOIN")
                    meta.usage_count += 1

    def _resolve_column_key(self, column_node: exp.Column) -> Tuple[Optional[str], Optional[str]]:
        """Определяет уникальный ключ колонки и её алиас таблицы.

        Алгоритм:
        1. Извлекаем ссылку на таблицу и имя колонки из AST узла.
        2. Обрабатываем специальный случай "*" (звёздочка).
        3. Если таблица не указана, проверяем, является ли колонка алиасом из SELECT.
        4. Если колонка является алиасом в ORDER BY, игнорируем её (чтобы не создавать синтетические колонки).
        5. Если таблица указана:
           - Проверяем маппинги подзапросов и CTE.
           - Ищем таблицу в текущей области видимости (scope) по алиасу.
           - Формируем ключ как "таблица.колонка".
        6. Если таблица не указана, пытаемся определить единственную таблицу в области видимости.
        7. Если таблицу определить не удалось, возвращаем ключ с префиксом "UNKNOWN".

        Args:
            column_node: Узел AST колонки (sqlglot.exp.Column).

        Returns:
            Кортеж (уникальный ключ колонки, алиас таблицы или None).
        """
        table_ref = column_node.table
        col_name = column_node.name
        # sqlglot использует "_star_" для звёздочки в AST
        if col_name == "_star_":
            col_name = "*"
        if not col_name:
            return None, None

        # Если таблица не указана, но колонка является алиасом из SELECT (например, "col AS alias")
        if not table_ref and col_name in self.column_alias_to_source:
            return self.column_alias_to_source[col_name], None

        # ORDER BY aliases should not create synthetic UNKNOWN columns.
        if not table_ref and col_name in self.select_aliases:
            return None, None

        if table_ref:
            # Проверяем маппинги подзапросов (например, column из подзапроса с алиасом)
            mapped_key = self.subquery_column_map.get((table_ref, col_name))
            if mapped_key:
                return mapped_key, table_ref

            # Проверяем маппинги CTE
            mapped_key = self.cte_column_map.get((table_ref, col_name))
            if mapped_key:
                return mapped_key, table_ref

            # Ищем таблицу в текущей области видимости
            scope = self._nearest_select_scope(column_node)
            table_name = None
            if scope and table_ref in scope.alias_to_table:
                table_name = scope.alias_to_table[table_ref]
            else:
                table_name = table_ref
            return f"{table_name}.{col_name}", table_ref

        # Таблица не указана, пытаемся вывести из контекста
        scope = self._nearest_select_scope(column_node)
        if scope and len(scope.tables) == 1:
            table_name = next(iter(scope.tables))
            return f"{table_name}.{col_name}", None

        # Не удалось определить таблицу – помечаем как UNKNOWN
        return f"UNKNOWN.{col_name}", None

    def _get_or_create_column(self, key: str, table_alias: Optional[str]) -> ColumnMetadata:
        if key in self.columns:
            meta = self.columns[key]
            if table_alias and not meta.table_alias:
                meta.table_alias = table_alias
            elif table_alias and meta.table_alias:
                # Если текущий table_alias является CTE, а новый - нет, то обновляем
                # (предпочтение отдаем не-CTE алиасам)
                current_is_cte = self._is_cte_table(meta.table_alias)
                new_is_cte = self._is_cte_table(table_alias)
                if current_is_cte and not new_is_cte:
                    meta.table_alias = table_alias
                # Если оба не CTE, оставляем как есть (первый установленный)
            return meta

        table_name, col_name = key.split(".", 1)
        meta = ColumnMetadata(
            column_name=col_name,
            table=None if table_name == "UNKNOWN" else table_name,
            table_alias=table_alias,
            full_name=key if table_name != "UNKNOWN" else col_name,
            aliases=[],
        )
        if table_alias:
            meta.aliases.append(f"{table_alias}.{meta.column_name}")
        if meta.table:
            table_obj = self._find_table_by_name(meta.table)
            if table_obj:
                table_obj.add_column(meta.full_name or key)
        self.columns[key] = meta
        return meta

    def _collect_subquery_and_cte_column_maps(self) -> None:
        """Собирает маппинги колонок подзапросов и CTE.

        Для каждого подзапроса (exp.Subquery) и CTE (exp.CTE) извлекает алиас и
        строит отображение (алиас_таблицы, имя_колонки) -> уникальный_ключ_колонки.
        Это позволяет позднее разрешать ссылки вида "alias.column" на исходные колонки.

        Алгоритм:
        1. Найти все подзапросы в AST.
        2. Для каждого подзапроса с алиасом и SELECT-телом вызвать _collect_projection_map,
           которая проецирует колонки SELECT на алиас.
        3. Аналогично для CTE.
        """
        for subquery in self.ast.find_all(exp.Subquery):
            sub_alias = subquery.alias_or_name
            if not sub_alias or not isinstance(subquery.this, exp.Select):
                continue
            self._collect_projection_map(sub_alias, subquery.this, self.subquery_column_map)

        for cte in self.ast.find_all(exp.CTE):
            cte_name = cte.alias_or_name
            if not cte_name or not isinstance(cte.this, exp.Select):
                continue
            self._collect_projection_map(cte_name, cte.this, self.cte_column_map)

    def _collect_projection_map(
        self,
        relation_alias: str,
        select_node: exp.Select,
        target_map: Dict[Tuple[str, str], str],
    ) -> None:
        """Строит отображение колонок CTE/подзапроса на исходные колонки.

        Для каждого выражения в SELECT (колонка, вычисление, функция) определяет
        выходное имя (алиас или имя колонки) и находит исходную колонку (source_column).
        Затем записывает в target_map маппинг (relation_alias, output_name) -> source_key.

        Также создаёт или обновляет метаданные колонки CTE/подзапроса, отмечая вычисляемые колонки.

        Args:
            relation_alias: Алиас CTE или подзапроса.
            select_node: Узел SELECT, представляющий тело CTE/подзапроса.
            target_map: Словарь для сохранения маппинга (subquery_column_map или cte_column_map).
        """
        for expression in select_node.args.get("expressions") or []:
            output_name = expression.alias_or_name
            if not output_name and isinstance(expression, exp.Column):
                output_name = expression.name
            if not output_name:
                continue
            source_column = next(expression.find_all(exp.Column), None)
            if not source_column:
                continue
            source_key, _ = self._resolve_column_key(source_column)
            if source_key:
                target_map[(relation_alias, output_name)] = source_key
                alias_hint = f"{relation_alias}.{output_name}"
                if source_key not in self.source_alias_hints:
                    self.source_alias_hints[source_key] = set()
                self.source_alias_hints[source_key].add(alias_hint)

                # Создаем колонку CTE/подзапроса для каждого алиаса
                cte_column_key = f"{relation_alias}.{output_name}"
                expr_for_calc = expression.this if isinstance(expression, exp.Alias) else expression
                is_calculation = self._expression_is_calculation(expr_for_calc)
                
                if cte_column_key in self.columns:
                    # Обновляем существующую колонку
                    meta = self.columns[cte_column_key]
                    if is_calculation:
                        meta.is_calculation = True
                        meta.calculation_type = self._calculation_type(expr_for_calc)
                        meta.calculation_expression = expr_for_calc.sql()
                    # Учитываем использование колонки в SELECT CTE
                    meta.usage_count += 1
                    if "SELECT" not in meta.usage_locations:
                        meta.usage_locations.append("SELECT")
                else:
                    # Создаем новую колонку
                    meta = ColumnMetadata(
                        column_name=output_name,
                        table=relation_alias,
                        table_alias=relation_alias,
                        full_name=cte_column_key,
                        aliases=[alias_hint],
                        is_calculation=is_calculation,
                        calculation_type=self._calculation_type(expr_for_calc) if is_calculation else None,
                        calculation_expression=expr_for_calc.sql() if is_calculation else None,
                    )
                    # Учитываем использование колонки в SELECT CTE
                    meta.usage_count = 1
                    meta.usage_locations.append("SELECT")
                    self.columns[cte_column_key] = meta
                    # Добавляем колонку в таблицу CTE
                    table_obj = self._find_table_by_name(relation_alias)
                    if table_obj:
                        table_obj.add_column(cte_column_key)
                
                # Добавляем зависимости на все исходные колонки в выражении
                for col in expr_for_calc.find_all(exp.Column):
                    col_key, _ = self._resolve_column_key(col)
                    if col_key and col_key not in meta.dependencies:
                        meta.dependencies.append(col_key)

    def _apply_source_alias_hints(self) -> None:
        for source_key, hints in self.source_alias_hints.items():
            meta = self.columns.get(source_key)
            if not meta:
                continue
            for hint in sorted(hints):
                if hint not in meta.aliases:
                    meta.aliases.append(hint)

            # If a column is exposed through subquery/CTE alias, hide base full-name alias.
            full_name_alias = meta.full_name or ""
            if full_name_alias and full_name_alias in meta.aliases:
                meta.aliases = [alias for alias in meta.aliases if alias != full_name_alias]

    def _detect_usage_context(self, node: exp.Column) -> List[str]:
        context: Set[str] = set()
        parent = node.parent
        owning_select = self._nearest_select_scope(node)
        while parent:
            if isinstance(parent, exp.Select):
                select_exprs = parent.args.get("expressions") or []
                if node in select_exprs:
                    context.add("SELECT")
            elif isinstance(parent, exp.Where):
                context.add("WHERE")
            elif isinstance(parent, exp.Join):
                context.add("JOIN")
            elif isinstance(parent, exp.Group):
                context.add("GROUP BY")
            elif isinstance(parent, exp.Having):
                context.add("HAVING")
            elif isinstance(parent, exp.Order):
                context.add("ORDER BY")
            elif isinstance(parent, exp.Alias):
                grandparent = parent.parent
                if isinstance(grandparent, exp.Select):
                    select_exprs = grandparent.args.get("expressions") or []
                    if parent in select_exprs:
                        context.add("SELECT")

            if self._expression_is_calculation(parent):
                context.add("calculation")
            if owning_select is not None and parent is owning_select:
                break
            parent = parent.parent
        return sorted(context) if context else ["UNKNOWN"]

    def _is_calculation_column(self, node: exp.Column) -> Tuple[bool, Optional[exp.Expression]]:
        parent = node.parent
        while parent:
            if self._expression_is_calculation(parent):
                return True, parent
            parent = parent.parent
        return False, None

    def _expression_is_calculation(self, expression: exp.Expression) -> bool:
        if isinstance(expression, CALCULATION_NODES):
            return True
        if isinstance(expression, exp.Func):
            # Boolean/logical operators in sqlglot also inherit Func (e.g. And),
            # so they must be excluded from calculation detection.
            if isinstance(expression, (exp.Connector, exp.Predicate)):
                return False
            return True
        return False

    def _calculation_type(self, parent: Optional[exp.Expression]) -> Optional[str]:
        if parent is None:
            return None
        if isinstance(parent, exp.AggFunc):
            return parent.__class__.__name__.upper()
        if isinstance(parent, (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod)):
            return "ARITHMETIC"
        if isinstance(parent, exp.Case):
            return "CASE"
        if isinstance(parent, exp.Cast):
            return "CAST"
        if isinstance(parent, exp.Anonymous):
            return (parent.name or "FUNCTION").upper()
        if isinstance(parent, exp.Func):
            return parent.__class__.__name__.upper()
        return parent.__class__.__name__.upper()

    def _nearest_select_scope(self, node: exp.Expression) -> Optional[ScopeInfo]:
        parent = node
        while parent:
            if isinstance(parent, exp.Select):
                return self.scope_by_select_id.get(id(parent))
            parent = parent.parent
        return None

    def _is_cte_table(self, table_name: str) -> bool:
        for cte in self.ast.find_all(exp.CTE):
            if cte.alias_or_name == table_name:
                return True
        return False

    def _find_table_by_name(self, table_name: str) -> Optional[TableInfo]:
        for (_, name, _), table in self.tables.items():
            if name == table_name:
                return table
        return None

    def _upsert_table(
        self,
        name: str,
        schema: Optional[str],
        alias: Optional[str],
        table_type: TableType,
    ) -> None:
        # Нормализация: пустая строка -> None
        if schema == "":
            schema = None
        if alias == "":
            alias = None
        key = (schema, name, table_type)
        if key not in self.tables:
            self.tables[key] = TableInfo(name=name, schema=schema, table_type=table_type)
        self.tables[key].add_alias(alias)

    def _render_columns_sample(self, columns: List[ColumnMetadata]) -> str:
        lines = [
            "Полное имя | Алиасы | Таблица | Где используется | Количество упоминаний",
            "-" * 85,
        ]
        for col in sorted(columns, key=lambda c: (c.table or "", c.column_name)):
            lines.append(
                f"{col.full_name} | {', '.join(col.aliases)} | {col.table or ''} | "
                f"{', '.join(col.usage_locations)} | {col.usage_count}"
            )
        return "\n".join(lines)