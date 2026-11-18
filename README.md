# 🏛️ Nemr DB Architect (المهندس الذكي لقواعد البيانات)

Autonomous relational database architecture, SQL query index optimization, and zero-downtime migration engine.

## 🚀 Overview

- **MySQL 8 & PostgreSQL Schema Synthesis**: Generates strict, normalized DDL schemas with automatic foreign keys, primary keys, and timestamp columns.
- **SQL Query Analyzer & Missing Index Hunter**: Detects filesort and table-scan bottlenecks in SQL queries and outputs exact `CREATE INDEX` recommendations.
- **Zero-Downtime Migrations**: Generates reversible, transactional UP / DOWN migrations for SQL and PHP PDO applications.

## 📦 Installation & Usage

```bash
cd nemr-db-architect
python cli.py design orders --fields "customer_id:int,total:decimal,status:string"
python cli.py optimize "SELECT * FROM orders WHERE status = 'pending' ORDER BY id DESC"
python cli.py migration create_orders --up "CREATE TABLE..." --down "DROP TABLE..."
```

## 🧪 Testing

```bash
python -m unittest discover -s tests
```
