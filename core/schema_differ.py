"""
Nemr DB Architect - Reversible SQL Schema Differ (v3.0.0)
Compares two SQL DDL snapshots and synthesizes reversible UP / DOWN MySQL 8 or PostgreSQL migrations.
"""

from __future__ import annotations
from typing import Any, Dict, List
from core.erd_analyzer import ErdAnalyzer


class SchemaDiffer:
    """Computes table and column deltas between two SQL schemas and emits UP/DOWN DDL."""

    @classmethod
    def _extract_raw_tables(cls, sql: str) -> Dict[str, str]:
        raw_map: Dict[str, str] = {}
        for tname, body, tail in ErdAnalyzer._iter_create_tables(sql):
            tail_str = tail.strip()
            ddl = f"CREATE TABLE `{tname}` ({body})" if not tail_str else f"CREATE TABLE `{tname}` ({body}) {tail_str}"
            raw_map[tname.lower()] = ddl + ";"
        return raw_map

    @classmethod
    def diff_schemas(
        cls,
        old_sql: str,
        new_sql: str,
        dialect: str = "mysql",
    ) -> Dict[str, Any]:
        old_parsed = ErdAnalyzer.parse_sql_schema(old_sql)["tables"]
        new_parsed = ErdAnalyzer.parse_sql_schema(new_sql)["tables"]
        raw_new = cls._extract_raw_tables(new_sql)
        raw_old = cls._extract_raw_tables(old_sql)

        is_pg = dialect.lower() == "postgres"
        q = '"' if is_pg else "`"

        up_stmts: List[str] = []
        down_stmts: List[str] = []
        summary: List[str] = []

        # 1. Added tables
        for tname in new_parsed:
            if tname not in old_parsed:
                summary.append(f"ADD TABLE {tname}")
                create_ddl = raw_new.get(tname, f"CREATE TABLE {q}{tname}{q} (id INT PRIMARY KEY);")
                if is_pg:
                    create_ddl = create_ddl.replace("`", '"')
                up_stmts.append(create_ddl)
                down_stmts.append(f"DROP TABLE IF EXISTS {q}{tname}{q};")

        # 2. Dropped tables
        for tname in old_parsed:
            if tname not in new_parsed:
                summary.append(f"DROP TABLE {tname}")
                up_stmts.append(f"DROP TABLE IF EXISTS {q}{tname}{q};")
                restore_ddl = raw_old.get(tname, f"CREATE TABLE {q}{tname}{q} (id INT PRIMARY KEY);")
                if is_pg:
                    restore_ddl = restore_ddl.replace("`", '"')
                down_stmts.append(restore_ddl)

        # 3. Column diffs on surviving tables
        for tname, new_tbl in new_parsed.items():
            if tname not in old_parsed:
                continue
            old_cols = {c["name"]: c for c in old_parsed[tname]["columns"]}
            new_cols = {c["name"]: c for c in new_tbl["columns"]}

            for cname, ncol in new_cols.items():
                null_kw = "NULL" if ncol["nullable"] else "NOT NULL"
                if cname not in old_cols:
                    summary.append(f"ADD COLUMN {tname}.{cname} ({ncol['type']})")
                    up_stmts.append(f"ALTER TABLE {q}{tname}{q} ADD COLUMN {q}{cname}{q} {ncol['type']} {null_kw};")
                    down_stmts.append(f"ALTER TABLE {q}{tname}{q} DROP COLUMN {q}{cname}{q};")
                else:
                    ocol = old_cols[cname]
                    if ocol["type"] != ncol["type"] or ocol["nullable"] != ncol["nullable"]:
                        old_null_kw = "NULL" if ocol["nullable"] else "NOT NULL"
                        summary.append(
                            f"ALTER COLUMN {tname}.{cname}: {ocol['type']} -> {ncol['type']}"
                        )
                        if is_pg:
                            up_stmts.append(f"ALTER TABLE {q}{tname}{q} ALTER COLUMN {q}{cname}{q} TYPE {ncol['type']};")
                            down_stmts.append(f"ALTER TABLE {q}{tname}{q} ALTER COLUMN {q}{cname}{q} TYPE {ocol['type']};")
                        else:
                            up_stmts.append(f"ALTER TABLE {q}{tname}{q} MODIFY COLUMN {q}{cname}{q} {ncol['type']} {null_kw};")
                            down_stmts.append(f"ALTER TABLE {q}{tname}{q} MODIFY COLUMN {q}{cname}{q} {ocol['type']} {old_null_kw};")

            for cname, ocol in old_cols.items():
                if cname not in new_cols:
                    old_null_kw = "NULL" if ocol["nullable"] else "NOT NULL"
                    summary.append(f"DROP COLUMN {tname}.{cname}")
                    up_stmts.append(f"ALTER TABLE {q}{tname}{q} DROP COLUMN {q}{cname}{q};")
                    down_stmts.append(f"ALTER TABLE {q}{tname}{q} ADD COLUMN {q}{cname}{q} {ocol['type']} {old_null_kw};")

        return {
            "has_changes": len(summary) > 0,
            "dialect": dialect.lower(),
            "summary": summary,
            "up_sql": "\n".join(up_stmts),
            "down_sql": "\n".join(down_stmts),
        }
