"""
Nemr DB Architect - SQL Query Optimizer & Missing Index Hunter
Parses SQL queries, analyzes execution patterns, and suggests optimal indexes to eliminate table scans.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Set, Any


@dataclass
class IndexRecommendation:
    table: str
    columns: List[str]
    index_name: str
    sql: str
    reason: str
    estimated_speedup: str


class QueryOptimizer:
    """Analyzes SQL queries and produces optimal composite and covering indexes."""

    @classmethod
    def analyze_query(cls, sql: str) -> Dict[str, Any]:
        cleaned = re.sub(r"\s+", " ", sql).strip()

        # Extract main table
        table_match = re.search(r"\bFROM\s+[`\"]?([a-zA-Z0-9_]+)[`\"]?", cleaned, re.IGNORECASE)
        main_table = table_match.group(1) if table_match else "unknown_table"

        # Extract WHERE columns
        where_cols: Set[str] = set()
        where_match = re.search(r"\bWHERE\b(.*?)(?:\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|$)", cleaned, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            # Find identifiers before =, !=, >, <, LIKE, IN
            found_cols = re.findall(r"[`\"]?([a-zA-Z0-9_]+)[`\"]?\s*(?:=|<|>|<=|>=|!=|LIKE|IN\b)", where_clause, re.IGNORECASE)
            for c in found_cols:
                if c.upper() not in ("AND", "OR", "NOT", "NULL", "SELECT"):
                    where_cols.add(c.lower())

        # Extract ORDER BY columns
        order_cols: List[str] = []
        order_match = re.search(r"\bORDER BY\s+(.*?)(?:\bLIMIT\b|$)", cleaned, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1)
            raw_orders = [o.strip() for o in order_clause.split(",")]
            for o in raw_orders:
                col_name = re.match(r"[`\"]?([a-zA-Z0-9_]+)[`\"]?", o)
                if col_name:
                    order_cols.append(col_name.group(1).lower())

        # Generate index recommendations
        recommendations: List[IndexRecommendation] = []
        ordered_cols_list = list(where_cols)

        # Composite index: WHERE columns first, then ORDER BY
        for oc in order_cols:
            if oc not in ordered_cols_list and oc != "id":
                ordered_cols_list.append(oc)

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
                    reason=f"Covers filtered WHERE columns ({', '.join(where_cols)}) and ORDER BY clauses, eliminating filesort and full table scans.",
                    estimated_speedup="10x - 100x on datasets > 50,000 rows"
                )
            )

        # Check for bad patterns
        warnings: List[str] = []
        if re.search(r"\bLIKE\s+['\"]%", cleaned, re.IGNORECASE):
            warnings.append("Leading wildcard (LIKE '%text') invalidates B-Tree index lookup. Consider FULLTEXT index.")
        if re.search(r"\bSELECT\s+\*\s+FROM\b", cleaned, re.IGNORECASE):
            warnings.append("Using SELECT * forces buffer pool bloat and prevents index-only covering scans. Explicitly list columns.")
        if "OR" in (where_match.group(1) if where_match else "").upper():
            warnings.append("WHERE clause contains OR operator which may force index merge. Consider UNION ALL.")

        return {
            "main_table": main_table,
            "where_columns": list(where_cols),
            "order_columns": order_cols,
            "recommendations": recommendations,
            "warnings": warnings,
            "is_optimized": len(recommendations) == 0 and len(warnings) == 0,
        }
