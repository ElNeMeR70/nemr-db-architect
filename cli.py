#!/usr/bin/env python3
"""
Nemr DB Architect - Unified CLI
Enterprise relational database schema design, SQL query indexing, and zero-downtime migrations.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.schema_designer import SchemaDesigner
from core.query_optimizer import QueryOptimizer
from core.migration_generator import MigrationGenerator


def cmd_design(args: argparse.Namespace) -> None:
    table_name = args.table
    fields_raw = args.fields.split(",") if args.fields else []
    fields = {}
    for f in fields_raw:
        if ":" in f:
            k, v = f.split(":", 1)
            fields[k.strip()] = v.strip()
        else:
            fields[f.strip()] = "string"

    print(f"\n🏛️ Designing Relational Schema for Table: `{table_name}` ({args.dialect.upper()})...\n")
    tbl = SchemaDesigner.design_table(table_name, fields, dialect=args.dialect, include_soft_delete=args.soft_delete)
    ddl = SchemaDesigner.generate_ddl(tbl, dialect=args.dialect)

    print("=" * 60)
    print(ddl)
    print("=" * 60)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(ddl, encoding="utf-8")
        print(f"\n✓ Saved DDL to: {out_path}\n")


def cmd_optimize(args: argparse.Namespace) -> None:
    sql = args.sql
    print(f"\n🔍 Analyzing SQL Query for Index Optimization...\n")
    res = QueryOptimizer.analyze_query(sql)

    print(f"Target Table: `{res['main_table']}`")
    print(f"WHERE Columns: {res['where_columns']}")
    print(f"ORDER BY Columns: {res['order_columns']}")

    if res['warnings']:
        print("\n⚠️ Performance Warnings:")
        for w in res['warnings']:
            print(f"  - {w}")

    if res['recommendations']:
        print("\n💡 Recommended Indexes:")
        for rec in res['recommendations']:
            print(f"  • {rec.sql}")
            print(f"    Reason: {rec.reason}")
            print(f"    Expected Speedup: {rec.estimated_speedup}\n")
    else:
        print("\n✓ Query appears well-structured or does not require additional indexes.\n")


def cmd_migration(args: argparse.Namespace) -> None:
    name = args.name
    up = args.up or "SELECT 1;"
    down = args.down or "SELECT 1;"
    fmt = args.format

    print(f"\n⚡ Generating Atomic Migration: '{name}'...\n")
    files = MigrationGenerator.generate_migration(name, up, down, format_type=fmt)
    for fname, content in files.items():
        out_dir = Path(args.dest or "./migrations")
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / fname
        file_path.write_text(content, encoding="utf-8")
        print(f"  ✓ Created: {file_path}")
    print("\n✓ Migration generated successfully.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nemr DB Architect: Enterprise Relational Database Brain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # design
    p_design = subparsers.add_parser("design", help="Design table schema & DDL")
    p_design.add_argument("table", type=str, help="Table name")
    p_design.add_argument("--fields", type=str, default="", help="Fields list e.g. name:string,price:float,user_id:int")
    p_design.add_argument("--dialect", type=str, default="mysql", choices=["mysql", "postgres"], help="SQL dialect")
    p_design.add_argument("--soft-delete", action="store_true", help="Include deleted_at column")
    p_design.add_argument("--out", type=str, default=None, help="Output file path")
    p_design.set_defaults(func=cmd_design)

    # optimize
    p_opt = subparsers.add_parser("optimize", help="Analyze SQL query and recommend indexes")
    p_opt.add_argument("sql", type=str, help="SQL query string")
    p_opt.set_defaults(func=cmd_optimize)

    # migration
    p_mig = subparsers.add_parser("migration", help="Generate UP/DOWN database migration")
    p_mig.add_argument("name", type=str, help="Migration name (e.g. create_orders_table)")
    p_mig.add_argument("--up", type=str, default="", help="UP SQL statement")
    p_mig.add_argument("--down", type=str, default="", help="DOWN SQL statement")
    p_mig.add_argument("--format", type=str, default="sql", choices=["sql", "php"], help="Format")
    p_mig.add_argument("--dest", type=str, default="./migrations", help="Destination folder")
    p_mig.set_defaults(func=cmd_migration)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
