#!/usr/bin/env python3
"""Test script to verify imports and parser functionality."""

import sys
import traceback

def test_imports():
    modules = [
        'sqlglot',
        'sqlglot.expressions',
        'sqlglot.dialects',
        'pandas',
        'openpyxl',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'core.parser_strategy',
        'core.column_analyzer',
        'models.sql_metadata',
        'ui.main_window',
    ]
    
    for mod in modules:
        try:
            __import__(mod)
            print(f"OK {mod}")
        except ImportError as e:
            print(f"FAIL {mod}: {e}")
            traceback.print_exc()
            return False
    
    return True

def test_parser():
    try:
        from core.parser_factory import ParserFactory
        from core.sql_dialect import SQLDialect
        
        parser = ParserFactory.create_parser("sqlglot", dialect=SQLDialect.ORACLE)
        sql = "SELECT a FROM b"
        metadata = parser.parse(sql)
        print(f"Parser test passed: columns={len(metadata.columns)}, tables={len(metadata.tables)}")
        return True
    except Exception as e:
        print(f"Parser test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing imports...")
    if not test_imports():
        sys.exit(1)
    print("\nTesting parser...")
    if not test_parser():
        sys.exit(1)
    print("\nAll tests passed.")