"""
Nemr DB Architect - Synthetic SQL Seed Data Generator (v2.0.0)
Generates realistic multi-row INSERT statements for MySQL 8 and PostgreSQL development & benchmarking.
"""

from __future__ import annotations
import uuid
from typing import Dict, List


class SeederGenerator:
    """Synthesizes deterministic, realistic multi-row SQL INSERT seed scripts."""

    STATUSES = ["active", "pending", "completed", "paid"]

    @classmethod
    def _sample_value(cls, field_name: str, field_type: str, row_idx: int, dialect: str) -> str:
        fname = field_name.lower()
        ftype = field_type.lower()
        is_pg = dialect.lower() == "postgres"

        if fname == "uuid" or ftype == "uuid":
            return f"'{uuid.uuid5(uuid.NAMESPACE_DNS, f'{fname}-{row_idx}')}'"
        if "email" in fname:
            return f"'user{row_idx}@elnemer-ai.com'"
        if "phone" in fname or "mobile" in fname:
            return f"'+2010{10000000 + row_idx:08d}'"
        if "status" in fname:
            return f"'{cls.STATUSES[(row_idx - 1) % len(cls.STATUSES)]}'"
        if "currency" in fname:
            return "'EGP'" if row_idx % 2 == 1 else "'USD'"
        if any(k in fname for k in ("price", "amount", "total", "balance", "cost")) or ftype in ("float", "decimal"):
            return f"{(99.50 + row_idx * 25.75):.2f}"
        if ftype in ("bool", "boolean") or fname.startswith("is_"):
            val = (row_idx % 2 == 1)
            return ("TRUE" if val else "FALSE") if is_pg else ("1" if val else "0")
        if ftype in ("int", "integer", "bigint") or fname.endswith("_id"):
            return str(100 + row_idx)
        if ftype == "json":
            return f'\'{{"seed_index": {row_idx}, "verified": true}}\''
        if "title" in fname or "name" in fname:
            return f"'Sample {field_name.replace('_', ' ').title()} #{row_idx}'"
        return f"'{field_name}_value_{row_idx}'"

    @classmethod
    def generate_sql_seed(
        cls,
        table_name: str,
        fields: Dict[str, str],
        rows: int = 10,
        dialect: str = "mysql",
    ) -> str:
        if not fields:
            raise ValueError("Fields dictionary cannot be empty when generating SQL seed data.")

        quote = '"' if dialect.lower() == "postgres" else "`"
        col_names = list(fields.keys())
        cols_sql = ", ".join(f"{quote}{c}{quote}" for c in col_names)

        value_rows: List[str] = []
        for idx in range(1, max(1, rows) + 1):
            vals = [cls._sample_value(c, fields[c], idx, dialect) for c in col_names]
            value_rows.append(f"  ({', '.join(vals)})")

        header = f"-- Seed data for {table_name} ({rows} rows, {dialect.upper()})"
        insert_stmt = f"INSERT INTO {quote}{table_name.lower()}{quote} ({cols_sql}) VALUES\n" + ",\n".join(value_rows) + ";"
        return f"{header}\n{insert_stmt}"
