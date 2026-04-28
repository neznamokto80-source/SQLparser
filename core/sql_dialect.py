"""
SQL dialects enumeration.
"""

from __future__ import annotations

from enum import Enum


class SQLDialect(Enum):
    """Supported SQL dialects."""

    ORACLE = "oracle"
    POSTGRESQL = "postgres"
    MYSQL = "mysql"
    SQLSERVER = "tsql"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    SQLITE = "sqlite"
    CLICKHOUSE = "clickhouse"
    REDSHIFT = "redshift"
    DATABRICKS = "databricks"
    HIVE = "hive"
    PRESTO = "presto"
    TRINO = "trino"
    DUCKDB = "duckdb"
    TERADATA = "teradata"


def dialect_to_sqlglot(dialect: SQLDialect) -> str:
    """Convert internal dialect enum to sqlglot dialect string."""
    mapping = {
        SQLDialect.ORACLE: "oracle",
        SQLDialect.POSTGRESQL: "postgres",
        SQLDialect.MYSQL: "mysql",
        SQLDialect.SQLSERVER: "tsql",
        SQLDialect.SNOWFLAKE: "snowflake",
        SQLDialect.BIGQUERY: "bigquery",
        SQLDialect.SQLITE: "sqlite",
        SQLDialect.CLICKHOUSE: "clickhouse",
        SQLDialect.REDSHIFT: "redshift",
        SQLDialect.DATABRICKS: "databricks",
        SQLDialect.HIVE: "hive",
        SQLDialect.PRESTO: "presto",
        SQLDialect.TRINO: "trino",
        SQLDialect.DUCKDB: "duckdb",
        SQLDialect.TERADATA: "teradata",
    }
    return mapping.get(dialect, "oracle")