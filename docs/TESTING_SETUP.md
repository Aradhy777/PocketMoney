# ExpenseTrack & Fudo Database & Testing Environment Setup

This document outlines the database prerequisites and instructions for running the test suite across both local development (MariaDB) and enterprise relational backends (Microsoft SQL Server / Azure SQL Database).

---

## 1. Local Development (MariaDB)

### Prerequisites
- MariaDB 10.11+ or MySQL 8.0+ running on `127.0.0.1:3306`.
- PyMySQL installed (`pip install -r requirements.txt`).

### Running MariaDB Tests
```bash
python -m pytest -k "mariadb" -v
```
All MariaDB tests provision isolated, disposable databases (e.g., `et_p1c_test_*`, `et_p2a_maria_*`) using random UUIDs and drop them automatically upon test completion. The live database `expensetrack` is never mutated.

---

## 2. Microsoft SQL Server LocalDB (Windows Only)

### Prerequisites
1. **Operating System**: Microsoft Windows 10 / 11 / Windows Server.
2. **LocalDB Instance**: SQL Server LocalDB must be installed and running:
   ```cmd
   sqllocaldb create MSSQLLocalDB
   sqllocaldb start MSSQLLocalDB
   ```
3. **ODBC Driver**: Microsoft ODBC Driver 17 or 18 for SQL Server must be installed:
   - Download the official installer: `msodbcsql17.msi` or `msodbcsql18.msi` from Microsoft Learn.
   - Verify installation in Python:
     ```python
     import pyodbc
     print(pyodbc.drivers())
     # Expected: 'ODBC Driver 17 for SQL Server' or 'ODBC Driver 18 for SQL Server'
     ```

### Running LocalDB Tests on Windows
```bash
python -m pytest -k "localdb" -v
```

> [!NOTE]
> When executing on machines without Microsoft ODBC Driver 17/18 installed, LocalDB test cases will cleanly **skip** with an explanatory notice (`require_localdb`) rather than raising raw `IM002 Data source name not found` driver crashes.

---

## 3. Microsoft SQL Server & Azure SQL Database (Linux & Container Environments)

SQL Server LocalDB is a Windows-only feature. In Linux development, CI/CD pipelines, or containerized Docker deployments, testing against Microsoft SQL Server requires either a containerized SQL Server instance or a live Azure SQL Database.

### Linux / Docker Container Setup
In the production `Dockerfile`, Microsoft ODBC Driver 18 is bundled via standard Microsoft package repositories:
```dockerfile
RUN curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc \
    && curl https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

### Running Integration Tests Against Azure SQL or Remote SQL Server
Configure environment variables:
```bash
export DB_BACKEND=mssql
export DATABASE_URL="mssql+pyodbc://user:password@your-sql-server.database.windows.net:1433/expensetrack_test?driver=ODBC+Driver+18+for+SQL+Server"
python -m pytest tests/test_database_engine.py
```
