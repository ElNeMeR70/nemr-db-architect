---
name: nemr-db-architect
description: Autonomous relational database architecture engine (MySQL 8 & PostgreSQL). Synthesizes normalized schemas with foreign keys and composite indexes, detects missing indexes on slow queries, and generates atomic zero-downtime UP/DOWN migrations. Use when the user asks to design a database, optimize SQL queries, add database indexes, or generate database migrations.
---

# Nemr DB Architect (المهندس الذكي لقواعد البيانات)

Autonomous relational database architecture and query optimization engine for high-concurrency SaaS applications.

## Key Capabilities

1. **Auto-Schema Synthesizer (`design`)**:
   - Compiles natural language entity definitions into production-grade MySQL 8 and PostgreSQL DDL.
   - Automatically provisions `BIGINT UNSIGNED AUTO_INCREMENT` / `BIGSERIAL` primary keys, foreign key constraints with `ON DELETE CASCADE`, composite indexes, and ISO timestamps.
   - Supports soft-delete patterns (`deleted_at`).

2. **Query Optimizer & Index Hunter (`optimize`)**:
   - Analyzes SQL queries, detects table scan hazards (leading wildcards `%`, `SELECT *`, unindexed `WHERE` and `ORDER BY` clauses).
   - Generates exact composite `CREATE INDEX` recommendations with performance speedup estimates.

3. **Atomic Migration Generator (`migration`)**:
   - Generates atomic UP and DOWN migration files with transaction isolation wrappers in pure SQL or PHP (PDO).

## CLI Quick Reference

```bash
# 1. Design MySQL Schema
python cli.py design products --fields "title:string,price:decimal,stock:int,category_id:int" --out schema.sql

# 2. Design PostgreSQL Schema with Soft Delete
python cli.py design invoices --fields "amount:float,customer_email:string,status:string" --dialect postgres --soft-delete

# 3. Analyze & Optimize Slow SQL Query
python cli.py optimize "SELECT id, total FROM orders WHERE status = 'pending' AND user_id = 45 ORDER BY created_at DESC"

# 4. Generate Zero-Downtime Migration
python cli.py migration add_status_to_users --up "ALTER TABLE users ADD status VARCHAR(50);" --down "ALTER TABLE users DROP COLUMN status;" --format php
```
