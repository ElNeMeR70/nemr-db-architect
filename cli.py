#!/usr/bin/env python3
"""
Nemr DB Architect v3.0.0 - Unified CLI (Sovereign Edition)
Enterprise relational database schema design, reversible schema diffing, PHP 8.3 PDO repository synthesis,
ESR query optimization, DDL auditing + Mermaid ERDs, and synthetic SQL seeding.
"""

from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.schema_designer import SchemaDesigner
from core.query_optimizer import QueryOptimizer
from core.migration_generator import MigrationGenerator
from core.erd_analyzer import ErdAnalyzer
from core.seeder_generator import SeederGenerator
from core.schema_differ import SchemaDiffer
from core.pdo_repository_gen import PdoRepositoryGenerator

VERSION = "3.0.0"


def _parse_fields(fields_arg: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for f in (fields_arg.split(",") if fields_arg else []):
        if ":" in f:
            k, v = f.split(":", 1)
            fields[k.strip()] = v.strip()
        elif f.strip():
            fields[f.strip()] = "string"
    return fields


def cmd_design(args: argparse.Namespace) -> None:
    table_name = args.table
    fields = _parse_fields(args.fields)

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
    res = QueryOptimizer.analyze_query(args.sql)
    if args.json:
        payload = {
            **res,
            "recommendations": [asdict(r) for r in res["recommendations"]],
            "join_recommendations": [asdict(r) for r in res["join_recommendations"]],
        }
        print(json.dumps(payload, indent=2))
        return

    print("\n🔍 Analyzing SQL Query with ESR Engine & JOIN Analyzer...\n")
    print(f"Target Table: `{res['main_table']}`")
    print(f"WHERE Columns: {res['where_columns']}")
    print(f"ORDER BY Columns: {res['order_columns']}")
    print(f"Optimal ESR Order: {res['esr_order']}")

    if res["warnings"]:
        print("\n⚠️ Performance Warnings:")
        for w in res["warnings"]:
            print(f"  - {w}")

    if res["rewrites"]:
        print("\n✍️ Suggested Sargable Query Rewrites:")
        for rw in res["rewrites"]:
            print(f"  -> {rw}")

    if res["recommendations"]:
        print("\n💡 Recommended Composite Indexes:")
        for rec in res["recommendations"]:
            print(f"  • {rec.sql}")
            print(f"    Reason: {rec.reason}")
            print(f"    Expected Speedup: {rec.estimated_speedup}")

    if res["join_recommendations"]:
        print("\n🔗 Recommended JOIN Foreign-Key Indexes:")
        for rec in res["join_recommendations"]:
            print(f"  • {rec.sql}")
            print(f"    Reason: {rec.reason}")

    if not res["recommendations"] and not res["join_recommendations"] and not res["warnings"]:
        print("\n✓ Query appears well-structured or does not require additional indexes.")
    print()


def cmd_migration(args: argparse.Namespace) -> None:
    files = MigrationGenerator.generate_migration(args.name, args.up or "SELECT 1;", args.down or "SELECT 1;", format_type=args.format)
    print(f"\n⚡ Generating Atomic Migration: '{args.name}'...\n")
    for fname, content in files.items():
        out_dir = Path(args.dest or "./migrations")
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / fname
        file_path.write_text(content, encoding="utf-8")
        print(f"  ✓ Created: {file_path}")
    print("\n✓ Migration generated successfully.\n")


def cmd_audit_schema(args: argparse.Namespace) -> None:
    sql_path = Path(args.sql_file)
    if not sql_path.exists():
        print(f"Error: SQL file '{sql_path}' not found.")
        sys.exit(1)

    sql = sql_path.read_text(encoding="utf-8", errors="ignore")
    findings = ErdAnalyzer.audit_schema(sql)
    erd = ErdAnalyzer.generate_mermaid_erd(sql)

    if args.json:
        print(json.dumps({"findings": findings, "mermaid_erd": erd}, indent=2))
        return

    print(f"\n🩺 Schema Audit Report for `{sql_path.name}`:\n" + "=" * 60)
    if findings:
        for f in findings:
            print(f"  [{f['severity']}] Table `{f['table']}` ({f['issue']}): {f['fix']}")
    else:
        print("  ✓ 0 schema anti-patterns detected!")

    print("\n📊 Mermaid ERD Preview:\n" + "-" * 60)
    print(erd)
    print("=" * 60)

    if args.erd:
        erd_path = Path(args.erd)
        erd_path.write_text(f"# Database ERD\n\n```mermaid\n{erd}\n```\n", encoding="utf-8")
        print(f"\n✓ Saved Mermaid ERD to: {erd_path}\n")


def cmd_seed(args: argparse.Namespace) -> None:
    fields = _parse_fields(args.fields)
    if not fields:
        print("Error: --fields is required (e.g. email:string,amount:decimal).")
        sys.exit(1)

    sql_seed = SeederGenerator.generate_sql_seed(args.table, fields, rows=args.rows, dialect=args.dialect)
    print(f"\n🌱 Synthetic SQL Seed ({args.rows} rows, {args.dialect.upper()}):\n" + "=" * 60)
    print(sql_seed)
    print("=" * 60)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(sql_seed, encoding="utf-8")
        print(f"\n✓ Saved seed script to: {out_path}\n")


def cmd_diff(args: argparse.Namespace) -> None:
    old_p = Path(args.old_sql)
    new_p = Path(args.new_sql)
    if not old_p.exists() or not new_p.exists():
        print("Error: Both old_sql and new_sql paths must exist.")
        sys.exit(1)

    diff_res = SchemaDiffer.diff_schemas(
        old_p.read_text(encoding="utf-8", errors="ignore"),
        new_p.read_text(encoding="utf-8", errors="ignore"),
        dialect=args.dialect,
    )
    if args.json:
        print(json.dumps(diff_res, indent=2))
        return

    print(f"\n🔄 Reversible Schema Diff ({args.dialect.upper()}):\n" + "=" * 60)
    for item in diff_res["summary"]:
        print(f"  • {item}")
    print("\n-- >>> UP >>>\n" + (diff_res["up_sql"] or "-- No changes"))
    print("\n-- >>> DOWN >>>\n" + (diff_res["down_sql"] or "-- No changes"))
    print("=" * 60)

    if args.out:
        out_p = Path(args.out)
        out_p.write_text(
            f"-- >>> UP >>>\n{diff_res['up_sql']}\n\n-- >>> DOWN >>>\n{diff_res['down_sql']}\n",
            encoding="utf-8",
        )
        print(f"\n✓ Saved reversible migration to: {out_p}\n")


def cmd_php_repo(args: argparse.Namespace) -> None:
    fields = _parse_fields(args.fields)
    if not fields:
        print("Error: --fields is required (e.g. email:string,amount:decimal).")
        sys.exit(1)

    php_code = PdoRepositoryGenerator.generate_repository(args.table, fields, namespace=args.namespace)
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(php_code, encoding="utf-8")
        print(f"\n✓ Generated PHP 8.3 PDO Repository in: {out_p}\n")
    else:
        print(php_code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nemr DB Architect v3.0.0: Sovereign Relational Database Brain")
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_design = subparsers.add_parser("design", help="Design table schema & DDL")
    p_design.add_argument("table", type=str, help="Table name")
    p_design.add_argument("--fields", type=str, default="", help="Fields list e.g. name:string,price:float,user_id:int")
    p_design.add_argument("--dialect", type=str, default="mysql", choices=["mysql", "postgres"], help="SQL dialect")
    p_design.add_argument("--soft-delete", action="store_true", help="Include deleted_at column")
    p_design.add_argument("--out", type=str, default=None, help="Output file path")
    p_design.set_defaults(func=cmd_design)

    p_opt = subparsers.add_parser("optimize", help="Analyze SQL query and recommend ESR & JOIN indexes")
    p_opt.add_argument("sql", type=str, help="SQL query string")
    p_opt.add_argument("--json", action="store_true", help="Emit JSON output")
    p_opt.set_defaults(func=cmd_optimize)

    p_mig = subparsers.add_parser("migration", help="Generate UP/DOWN database migration")
    p_mig.add_argument("name", type=str, help="Migration name")
    p_mig.add_argument("--up", type=str, default="", help="UP SQL statement")
    p_mig.add_argument("--down", type=str, default="", help="DOWN SQL statement")
    p_mig.add_argument("--format", type=str, default="sql", choices=["sql", "php"], help="Format")
    p_mig.add_argument("--dest", type=str, default="./migrations", help="Destination folder")
    p_mig.set_defaults(func=cmd_migration)

    p_audit = subparsers.add_parser("audit-schema", help="Audit SQL DDL file and generate Mermaid ERD")
    p_audit.add_argument("sql_file", type=str, help="Path to .sql schema file")
    p_audit.add_argument("--erd", type=str, default=None, help="Output Markdown path for Mermaid ERD")
    p_audit.add_argument("--json", action="store_true", help="Emit JSON output")
    p_audit.set_defaults(func=cmd_audit_schema)

    p_seed = subparsers.add_parser("seed", help="Generate realistic SQL INSERT seed rows")
    p_seed.add_argument("table", type=str, help="Target table name")
    p_seed.add_argument("--fields", type=str, required=True, help="Fields list")
    p_seed.add_argument("--rows", type=int, default=10, help="Number of seed rows")
    p_seed.add_argument("--dialect", type=str, default="mysql", choices=["mysql", "postgres"], help="SQL dialect")
    p_seed.add_argument("--out", type=str, default=None, help="Output .sql file path")
    p_seed.set_defaults(func=cmd_seed)

    p_diff = subparsers.add_parser("diff", help="Diff two SQL DDL schemas into reversible UP/DOWN migrations")
    p_diff.add_argument("old_sql", type=str, help="Baseline .sql schema")
    p_diff.add_argument("new_sql", type=str, help="Target .sql schema")
    p_diff.add_argument("--dialect", type=str, default="mysql", choices=["mysql", "postgres"], help="SQL dialect")
    p_diff.add_argument("--out", type=str, default=None, help="Output migration .sql path")
    p_diff.add_argument("--json", action="store_true", help="Emit JSON output")
    p_diff.set_defaults(func=cmd_diff)

    p_repo = subparsers.add_parser("php-repo", help="Generate PHP 8.3 readonly DTO + PDO Repository")
    p_repo.add_argument("table", type=str, help="Table name")
    p_repo.add_argument("--fields", type=str, required=True, help="Fields list e.g. email:string,amount:decimal")
    p_repo.add_argument("--namespace", type=str, default="App\\Repositories", help="PHP namespace")
    p_repo.add_argument("--out", type=str, default=None, help="Output .php path")
    p_repo.set_defaults(func=cmd_php_repo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
