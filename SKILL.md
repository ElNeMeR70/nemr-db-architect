---
name: nemr-db-architect
description: Autonomous relational database architecture engine v3.0.0 (MySQL 8 & PostgreSQL). Synthesizes normalized schemas with foreign keys and composite indexes, diffs two SQL DDL files into reversible UP/DOWN migrations, generates strict PHP 8.3 readonly DTO + PDO repositories, audits SQL DDL and emits Mermaid ERDs, recommends ESR-ordered & JOIN indexes with sargable rewrites, and builds SQL seed scripts. Use when designing, diffing, auditing, optimizing, or seeding databases.
---

# Nemr DB Architect v3.0.0 (المهندس الذكي لقواعد البيانات)

Autonomous relational database architecture, reversible schema diffing, PHP 8.3 PDO repository synthesis, ESR query optimization, DDL auditing, Mermaid ERD generation, and SQL seeding engine.

## Key Capabilities

1. **Auto-Schema Synthesizer (`design`)**:
   - Compiles entity definitions into MySQL 8 and PostgreSQL DDL with `BIGINT UNSIGNED AUTO_INCREMENT` / `BIGSERIAL`, cascading foreign keys, composite indexes, and optional `deleted_at`.
2. **Reversible Schema Differ (`diff`)**:
   - Compares baseline vs target SQL DDL files and synthesizes atomic reversible `UP` / `DOWN` migrations (`CREATE TABLE`, `DROP TABLE`, `ADD COLUMN`, `DROP COLUMN`, `MODIFY COLUMN` / `ALTER COLUMN TYPE`) with `--json` support.
3. **PHP 8.3 PDO Repository Generator (`php-repo`)**:
   - Synthesizes immutable `readonly class <Entity>Record` DTOs and parameterized PDO CRUD + `inTransaction()` repositories immune to SQL injection.
4. **ESR & JOIN Query Optimizer (`optimize`)**:
   - Applies strict **Equality -> Sort -> Range (ESR)** index ordering, detects unindexed `JOIN` foreign keys, and suggests sargable rewrites for `YEAR()`, `DATE()`, and `LOWER()`.
5. **DDL Linter & Mermaid ERD Generator (`audit-schema`)**:
   - Flags missing primary keys, unindexed FKs, `FLOAT`/`DOUBLE` currency columns, and `MyISAM`/`utf8` hazards while emitting Mermaid `erDiagram` graphs.
6. **Atomic Migrations & Synthetic Seed Data (`migration`, `seed`)**:
   - Produces transactional SQL/PHP migrations and multi-row realistic `INSERT INTO` seed datasets.

## CLI Quick Reference

```bash
python cli.py --version
python cli.py design products --fields "title:string,price:decimal,category_id:int" --out schema.sql
python cli.py diff old_schema.sql new_schema.sql --dialect mysql --out 2026_alter.sql
python cli.py php-repo orders --fields "user_id:int,total:decimal,is_paid:bool" --out OrderRepository.php
python cli.py optimize "SELECT o.id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = 'paid' AND YEAR(o.created_at) = 2026 ORDER BY o.total DESC" --json
python cli.py audit-schema schema.sql --erd architecture_erd.md
python cli.py seed orders --fields "email:string,amount:decimal,is_paid:bool,status:string" --rows 10 --out seed.sql
```
