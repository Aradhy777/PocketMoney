"""
pytest configuration and shared test environment markers/fixtures.
Provides centralized helpers to detect whether Windows LocalDB and
Microsoft ODBC Driver 17/18 are available before attempting tests.
"""
from __future__ import annotations

import os
from typing import Optional
import pytest

_LOCALDB_AVAILABLE: Optional[bool] = None
_LOCALDB_REASON: str = ""


def check_localdb_support() -> tuple[bool, str]:
    """
    Check if the current test environment has:
    1. pyodbc installed
    2. Microsoft ODBC Driver 17 or 18 for SQL Server registered
    3. Windows LocalDB (localdb)\\MSSQLLocalDB reachable
    """
    global _LOCALDB_AVAILABLE, _LOCALDB_REASON
    if _LOCALDB_AVAILABLE is not None:
        return _LOCALDB_AVAILABLE, _LOCALDB_REASON

    try:
        import pyodbc
    except ImportError:
        _LOCALDB_AVAILABLE = False
        _LOCALDB_REASON = "pyodbc is not installed in the environment."
        return _LOCALDB_AVAILABLE, _LOCALDB_REASON

    drivers = set(pyodbc.drivers())
    supported_driver = None
    for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if d in drivers:
            supported_driver = d
            break

    if not supported_driver:
        _LOCALDB_AVAILABLE = False
        _LOCALDB_REASON = (
            f"Microsoft ODBC Driver 17/18 for SQL Server not found in pyodbc.drivers() (available: {list(drivers)}). "
            "Install 'msodbcsql17' or 'msodbcsql18' on Windows to enable LocalDB integration tests."
        )
        return _LOCALDB_AVAILABLE, _LOCALDB_REASON

    conn_str = (
        f"DRIVER={{{supported_driver}}};"
        "SERVER=(localdb)\\MSSQLLocalDB;"
        "DATABASE=master;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=2)
        conn.close()
        _LOCALDB_AVAILABLE = True
        _LOCALDB_REASON = f"Connected successfully via {supported_driver}."
    except Exception as exc:
        _LOCALDB_AVAILABLE = False
        _LOCALDB_REASON = f"SQL Server LocalDB instance '(localdb)\\MSSQLLocalDB' unreachable: {exc}"

    return _LOCALDB_AVAILABLE, _LOCALDB_REASON


def require_localdb():
    """Skip test cleanly with actionable documentation if LocalDB environment is missing."""
    avail, reason = check_localdb_support()
    if not avail:
        pytest.skip(f"SQL Server LocalDB environment unavailable: {reason}")
