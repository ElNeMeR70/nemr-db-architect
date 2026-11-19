"""
Nemr DB Architect - SQL Schema Parser, Linter & Mermaid ERD Analyzer
Parses MySQL 8 and PostgreSQL DDL files, audits anti-patterns, and emits Mermaid erDiagram code.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Set


class ErdAnalyzer:
    """Parses SQL DDL scripts, audits schema quality, and generates Mermaid ERDs."""

    CREATE_TABLE_HEAD_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*\(",
        re.IGNORECASE,
    )
    CREATE_INDEX_RE = re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?([a-zA-Z0-9_]+)[`\"]?\s+ON\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    @classmethod
    def _iter_create_tables(cls, sql: str) -> List[tuple[str, str, str]]:
        """Finds each CREATE TABLE using balanced-parenthesis scanning."""
        results: List[tuple[str, str, str]] = []
        pos = 0
        while True:
            m = cls.CREATE_TABLE_HEAD_RE.search(sql, pos)
            if not m:
                break
            table_name = m.group(1)
            idx = m.end()
            depth = 1
            in_sq = False
            in_dq = False
            while idx < len(sql) and depth > 0:
                ch = sql[idx]
                if ch == "'" and not in_dq:
                    in_sq = not in_sq
                elif ch == '"' and not in_sq:
                    in_dq = not in_dq
                elif not in_sq and not in_dq:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                idx += 1
            if depth == 0:
                body = sql[m.end():idx - 1]
                semi = sql.find(";", idx)
                tail = sql[idx:semi] if semi != -1 else sql[idx:]
                results.append((table_name, body, tail))
                pos = semi + 1 if semi != -1 else idx
            else:
                break
        return results

    @classmethod
    def _split_top_level_clauses(cls, body: str) -> List[str]:
        """Splits table body by top-level commas, respecting parentheses like DECIMAL(12, 2)."""
        clauses: List[str] = []
        buf: List[str] = []
        depth = 0
        in_sq = False
        in_dq = False

        for ch in body:
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif not in_sq and not in_dq:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth = max(0, depth - 1)
                elif ch == "," and depth == 0:
                    clause = "".join(buf).strip()
                    if clause:
                        clauses.append(clause)
                    buf = []
                    continue
            buf.append(ch)

        tail = "".join(buf).strip()
        if tail:
            clauses.append(tail)
        return clauses

    @classmethod
    def parse_sql_schema(cls, sql: str) -> Dict[str, Any]:
        tables: Dict[str, Dict[str, Any]] = {}

        # Strip SQL -- comments
        clean_sql = re.sub(r"--[^\r\n]*", "", sql)

        for raw_name, body, tail in cls._iter_create_tables(clean_sql):
            table_name = raw_name.lower()

            columns: List[Dict[str, Any]] = []
            foreign_keys: List[Dict[str, str]] = []
            indexed_cols: Set[str] = set()
            pk_cols: Set[str] = set()

            for clause in cls._split_top_level_clauses(body):
                upper = clause.upper().strip()

                # Table-level PRIMARY KEY
                if upper.startswith("PRIMARY KEY"):
                    m_pk = re.search(r"\(([^)]+)\)", clause)
                    if m_pk:
                        for c in m_pk.group(1).split(","):
                            col_id = c.strip().strip("`\"").lower()
                            pk_cols.add(col_id)
                            indexed_cols.add(col_id)
                    continue

                # Foreign key constraint
                if "FOREIGN KEY" in upper:
                    m_fk = re.search(
                        r"FOREIGN\s+KEY\s*\([`\"]?([a-zA-Z0-9_]+)[`\"]?\)\s*REFERENCES\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*\([`\"]?([a-zA-Z0-9_]+)[`\"]?\)",
                        clause,
                        re.IGNORECASE,
                    )
                    if m_fk:
                        foreign_keys.append({
                            "column": m_fk.group(1).lower(),
                            "ref_table": m_fk.group(2).lower(),
                            "ref_column": m_fk.group(3).lower(),
                        })
                    continue

                # Inline INDEX / KEY / UNIQUE KEY
                if upper.startswith(("INDEX ", "KEY ", "UNIQUE ", "CONSTRAINT ")):
                    m_idx = re.search(r"\(([^)]+)\)", clause)
                    if m_idx:
                        first_col = m_idx.group(1).split(",")[0].strip().strip("`\"").lower()
                        indexed_cols.add(first_col)
                    continue

                # Regular column definition
                col_match = re.match(r"^[`\"]?([a-zA-Z0-9_]+)[`\"]?\s+([a-zA-Z0-9_]+(?:\s*\([^)]+\))?)", clause)
                if col_match:
                    col_name = col_match.group(1).lower()
                    col_type = re.sub(r"\s+", "", col_match.group(2).upper())
                    is_pk = "PRIMARY KEY" in upper
                    is_unique = "UNIQUE" in upper
                    nullable = "NOT NULL" not in upper and not is_pk
                    if is_pk:
                        pk_cols.add(col_name)
                        indexed_cols.add(col_name)
                    if is_unique:
                        indexed_cols.add(col_name)

                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "is_pk": is_pk,
                        "is_unique": is_unique,
                        "nullable": nullable,
                    })

                    # Inline REFERENCES
                    m_inline_ref = re.search(
                        r"REFERENCES\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*\([`\"]?([a-zA-Z0-9_]+)[`\"]?\)",
                        clause,
                        re.IGNORECASE,
                    )
                    if m_inline_ref:
                        foreign_keys.append({
                            "column": col_name,
                            "ref_table": m_inline_ref.group(1).lower(),
                            "ref_column": m_inline_ref.group(2).lower(),
                        })

            # Mark table-level PKs on columns
            for col in columns:
                if col["name"] in pk_cols:
                    col["is_pk"] = True

            # Parse ENGINE & CHARSET
            eng_m = re.search(r"ENGINE\s*=\s*([a-zA-Z0-9_]+)", tail, re.IGNORECASE)
            cs_m = re.search(r"(?:DEFAULT\s+)?CHARSET\s*=\s*([a-zA-Z0-9_]+)", tail, re.IGNORECASE)

            tables[table_name] = {
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexed_columns": sorted(indexed_cols),
                "has_primary_key": len(pk_cols) > 0,
                "engine": eng_m.group(1) if eng_m else None,
                "charset": cs_m.group(1) if cs_m else None,
            }

        # Standalone CREATE INDEX statements
        for idx_m in cls.CREATE_INDEX_RE.finditer(clean_sql):
            tbl = idx_m.group(2).lower()
            cols_raw = idx_m.group(3).split(",")
            if tbl in tables and cols_raw:
                first_col = cols_raw[0].strip().strip("`\"").lower()
                if first_col not in tables[tbl]["indexed_columns"]:
                    tables[tbl]["indexed_columns"].append(first_col)

        return {"tables": tables}

    @classmethod
    def audit_schema(cls, sql: str) -> List[Dict[str, str]]:
        parsed = cls.parse_sql_schema(sql)
        findings: List[Dict[str, str]] = []
        money_names = ("price", "amount", "total", "balance", "cost", "salary", "fee", "revenue")

        for tname, tdata in parsed["tables"].items():
            # 1. Missing primary key
            if not tdata["has_primary_key"]:
                findings.append({
                    "severity": "CRITICAL",
                    "table": tname,
                    "issue": "MISSING_PRIMARY_KEY",
                    "fix": f"Add `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY to `{tname}` for InnoDB clustered index stability.",
                })

            # 2. Foreign key columns without an index
            indexed = set(tdata["indexed_columns"])
            for fk in tdata["foreign_keys"]:
                if fk["column"] not in indexed:
                    findings.append({
                        "severity": "HIGH",
                        "table": tname,
                        "issue": "MISSING_FK_INDEX",
                        "fix": f"CREATE INDEX `idx_{tname}_{fk['column']}` ON `{tname}` (`{fk['column']}`);",
                    })

            # 3. Monetary columns typed as FLOAT or DOUBLE
            for col in tdata["columns"]:
                cname = col["name"]
                ctype = col["type"]
                if any(m in cname for m in money_names) and (ctype.startswith("FLOAT") or ctype.startswith("DOUBLE") or ctype.startswith("REAL")):
                    findings.append({
                        "severity": "HIGH",
                        "table": tname,
                        "issue": "FLOAT_CURRENCY_PRECISION",
                        "fix": f"Change `{tname}`.`{cname}` from {ctype} to DECIMAL(12, 2) to eliminate floating-point rounding drift.",
                    })

            # 4. Legacy MyISAM or 3-byte utf8 charset
            engine = (tdata["engine"] or "").lower()
            charset = (tdata["charset"] or "").lower()
            if engine == "myisam":
                findings.append({
                    "severity": "MEDIUM",
                    "table": tname,
                    "issue": "LEGACY_ENGINE_OR_CHARSET",
                    "fix": f"ALTER TABLE `{tname}` ENGINE=InnoDB; (MyISAM lacks transactions and row-level locking).",
                })
            if charset == "utf8" or charset == "utf8mb3":
                findings.append({
                    "severity": "MEDIUM",
                    "table": tname,
                    "issue": "LEGACY_ENGINE_OR_CHARSET",
                    "fix": f"ALTER TABLE `{tname}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; (3-byte utf8 drops emojis/4-byte Arabic glyphs).",
                })

        return findings

    @classmethod
    def generate_mermaid_erd(cls, sql: str) -> str:
        parsed = cls.parse_sql_schema(sql)
        lines = ["erDiagram"]
        edges: List[str] = []

        for tname, tdata in parsed["tables"].items():
            fk_cols = {fk["column"] for fk in tdata["foreign_keys"]}
            lines.append(f"    {tname.upper()} {{")
            for col in tdata["columns"]:
                clean_type = re.sub(r"\([^)]*\)", "", col["type"]).lower()
                tags: List[str] = []
                if col["is_pk"]:
                    tags.append("PK")
                if col["name"] in fk_cols:
                    tags.append("FK")
                if col["is_unique"] and not col["is_pk"]:
                    tags.append("UK")
                tag_str = f' {",".join(tags)}' if tags else ""
                lines.append(f"        {clean_type} {col['name']}{tag_str}")
            lines.append("    }")

            for fk in tdata["foreign_keys"]:
                edges.append(f'    {fk["ref_table"].upper()} ||--o{{ {tname.upper()} : "{fk["column"]}"')

        if edges:
            lines.append("")
            lines.extend(edges)

        return "\n".join(lines)
