"""
Nemr DB Architect - SQL Query Optimizer & Missing Index Hunter (v2.0.0)
Implements ESR (Equality -> Sort -> Range) index ordering, JOIN index analysis, and sargable query rewrites.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class IndexRecommendation:
    table: str
    columns: List[str]
    index_name: str
    sql: str
    reason: str
    estimated_speedup: str


class QueryOptimizer:
    """Analyzes SQL queries and produces ESR-ordered composite and JOIN indexes."""

    @classmethod
    def analyze_query(cls, sql: str) -> Dict[str, Any]:
        cleaned = re.sub(r"\s+", " ", sql).strip()

        # Extract main table and optional alias
        table_match = re.search(
            r"\bFROM\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?",
            cleaned,
            re.IGNORECASE,
        )
        main_table = table_match.group(1) if table_match else "unknown_table"
        main_alias = None
        if table_match and table_match.group(2):
            candidate = table_match.group(2).upper()
            if candidate not in ("WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "ORDER", "GROUP", "LIMIT", "ON"):
                main_alias = table_match.group(2).lower()

        # Map aliases to table names for JOIN clauses
        alias_map: Dict[str, str] = {main_table.lower(): main_table.lower()}
        if main_alias:
            alias_map[main_alias] = main_table.lower()

        join_matches = list(
            re.finditer(
                r"\bJOIN\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?\s+ON\s+([^\s=]+)\s*=\s*([^\s]+)",
                cleaned,
                re.IGNORECASE,
            )
        )
        for jm in join_matches:
            jtable = jm.group(1).lower()
            alias_map[jtable] = jtable
            if jm.group(2) and jm.group(2).upper() != "ON":
                alias_map[jm.group(2).lower()] = jtable

        # Extract WHERE clause ESR columns deterministically
        equality_cols: List[str] = []
        range_cols: List[str] = []
        all_where_cols: List[str] = []

        where_match = re.search(r"\bWHERE\b(.*?)(?:\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|$)", cleaned, re.IGNORECASE)
        where_clause = where_match.group(1) if where_match else ""
        if where_clause:
            cond_pattern = re.compile(
                r"(?:[`\"]?[a-zA-Z0-9_]+[`\"]?\.)?[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*(=|!=|<>|<=|>=|<|>|LIKE\b|IN\b|BETWEEN\b)",
                re.IGNORECASE,
            )
            for m in cond_pattern.finditer(where_clause):
                col = m.group(1).lower()
                op = m.group(2).upper()
                if col in ("and", "or", "not", "null", "select", "year", "date", "lower", "upper"):
                    continue
                if col not in all_where_cols:
                    all_where_cols.append(col)
                if op in ("=", "IN"):
                    if col not in equality_cols:
                        equality_cols.append(col)
                else:
                    if col not in range_cols:
                        range_cols.append(col)

        # Extract ORDER BY columns
        order_cols: List[str] = []
        order_match = re.search(r"\bORDER BY\s+(.*?)(?:\bLIMIT\b|$)", cleaned, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1)
            for o in order_clause.split(","):
                o_clean = o.strip()
                col_name = re.match(r"(?:[`\"]?[a-zA-Z0-9_]+[`\"]?\.)?[`\"]?([a-zA-Z0-9_]+)[`\"]?", o_clean)
                if col_name:
                    cname = col_name.group(1).lower()
                    if cname not in order_cols:
                        order_cols.append(cname)

        # ESR Ordering: Equality -> Sort -> Range
        ordered_cols_list: List[str] = []
        for col in equality_cols:
            if col not in ordered_cols_list:
                ordered_cols_list.append(col)
        for col in order_cols:
            if col not in ordered_cols_list and col != "id":
                ordered_cols_list.append(col)
        for col in range_cols:
            if col not in ordered_cols_list:
                ordered_cols_list.append(col)

        recommendations: List[IndexRecommendation] = []
        if ordered_cols_list:
            cols_str = "_".join(ordered_cols_list[:3])
            idx_name = f"idx_{main_table}_{cols_str}"
            cols_sql = ", ".join(f"`{c}`" for c in ordered_cols_list)
            ddl = f"CREATE INDEX `{idx_name}` ON `{main_table}` ({cols_sql});"

            recommendations.append(
                IndexRecommendation(
                    table=main_table,
                    columns=ordered_cols_list,
                    index_name=idx_name,
                    sql=ddl,
                    reason=(
                        f"Follows ESR rule (Equality: {equality_cols or 'none'} -> Sort: {order_cols or 'none'} "
                        f"-> Range: {range_cols or 'none'}) to prevent filesort and full table scans."
                    ),
                    estimated_speedup="10x - 100x on datasets > 50,000 rows",
                )
            )

        # JOIN recommendations
        join_recommendations: List[IndexRecommendation] = []
        for jm in join_matches:
            jtable = jm.group(1).lower()
            for side in (jm.group(3), jm.group(4)):
                clean_side = side.strip().strip("`\"")
                if "." in clean_side:
                    ref_alias, ref_col = clean_side.split(".", 1)
                    resolved_table = alias_map.get(ref_alias.lower(), jtable)
                else:
                    resolved_table = jtable
                    ref_col = clean_side
                ref_col = ref_col.lower()
                if ref_col != "id":
                    j_idx = f"idx_{resolved_table}_{ref_col}"
                    j_sql = f"CREATE INDEX `{j_idx}` ON `{resolved_table}` (`{ref_col}`);"
                    join_recommendations.append(
                        IndexRecommendation(
                            table=resolved_table,
                            columns=[ref_col],
                            index_name=j_idx,
                            sql=j_sql,
                            reason=f"Indexes JOIN foreign-key `{resolved_table}`.`{ref_col}` to avoid nested-loop full scans.",
                            estimated_speedup="5x - 50x on multi-table joins",
                        )
                    )

        # Warnings & Non-sargable rewrites
        warnings: List[str] = []
        rewrites: List[str] = []

        if re.search(r"\bLIKE\s+['\"]%", cleaned, re.IGNORECASE):
            warnings.append("Leading wildcard (LIKE '%text') invalidates B-Tree index lookup. Consider FULLTEXT index.")
        if re.search(r"\bSELECT\s+\*\s+FROM\b", cleaned, re.IGNORECASE):
            warnings.append("Using SELECT * forces buffer pool bloat and prevents index-only covering scans. Explicitly list columns.")
        if re.search(r"\bOR\b", where_clause, re.IGNORECASE):
            warnings.append("WHERE clause contains OR operator which may force index merge. Consider UNION ALL.")

        # Detect non-sargable functions: YEAR(col) = 2026, DATE(col) = '...', LOWER(col) = '...'
        m_year = re.search(r"\bYEAR\s*\(\s*([a-zA-Z0-9_.`\"]+)\s*\)\s*=\s*(\d{4})", where_clause, re.IGNORECASE)
        if m_year:
            col_ref = m_year.group(1)
            yr = int(m_year.group(2))
            warnings.append(f"Non-sargable YEAR({col_ref}) prevents B-Tree index usage.")
            rewrites.append(f"Rewrite `YEAR({col_ref}) = {yr}` as `{col_ref} >= '{yr}-01-01' AND {col_ref} < '{yr + 1}-01-01'`.")

        m_date = re.search(r"\bDATE\s*\(\s*([a-zA-Z0-9_.`\"]+)\s*\)\s*=\s*['\"]([^'\"]+)['\"]", where_clause, re.IGNORECASE)
        if m_date:
            col_ref = m_date.group(1)
            dval = m_date.group(2)
            warnings.append(f"Non-sargable DATE({col_ref}) disables index range scans.")
            rewrites.append(f"Rewrite `DATE({col_ref}) = '{dval}'` as `{col_ref} >= '{dval} 00:00:00' AND {col_ref} <= '{dval} 23:59:59'`.")

        m_lower = re.search(r"\b(?:LOWER|UPPER)\s*\(\s*([a-zA-Z0-9_.`\"]+)\s*\)\s*=", where_clause, re.IGNORECASE)
        if m_lower:
            col_ref = m_lower.group(1)
            warnings.append(f"Non-sargable case function on {col_ref} disables standard index lookup.")
            rewrites.append(f"Use a case-insensitive collation (`utf8mb4_unicode_ci`) on {col_ref} or add a generated/functional index.")

        return {
            "main_table": main_table,
            "where_columns": all_where_cols,
            "order_columns": order_cols,
            "esr_order": ordered_cols_list,
            "recommendations": recommendations,
            "join_recommendations": join_recommendations,
            "warnings": warnings,
            "rewrites": rewrites,
            "is_optimized": len(recommendations) == 0 and len(join_recommendations) == 0 and len(warnings) == 0,
        }
