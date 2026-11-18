"""
Nemr DB Architect - Relational Schema Designer
Synthesizes normalized, production-grade MySQL 8 and PostgreSQL DDL schemas from high-level entity specs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ColumnDef:
    name: str
    col_type: str
    nullable: bool = False
    default: Optional[str] = None
    is_primary: bool = False
    auto_increment: bool = False
    is_unique: bool = False
    foreign_key: Optional[str] = None  # e.g. "users(id)"
    comment: str = ""


@dataclass
class TableDef:
    name: str
    columns: List[ColumnDef] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    collation: str = "utf8mb4_unicode_ci"


class SchemaDesigner:
    """Designs robust, normalized database schemas with best-practice indexing."""

    TYPE_MAP_MYSQL = {
        "id": "BIGINT UNSIGNED",
        "int": "INT",
        "bigint": "BIGINT",
        "string": "VARCHAR(255)",
        "text": "TEXT",
        "longtext": "LONGTEXT",
        "float": "DECIMAL(12, 2)",
        "decimal": "DECIMAL(12, 2)",
        "bool": "TINYINT(1)",
        "boolean": "TINYINT(1)",
        "timestamp": "TIMESTAMP",
        "datetime": "DATETIME",
        "json": "JSON",
        "uuid": "VARCHAR(36)",
    }

    TYPE_MAP_PGSQL = {
        "id": "BIGSERIAL",
        "int": "INTEGER",
        "bigint": "BIGINT",
        "string": "VARCHAR(255)",
        "text": "TEXT",
        "longtext": "TEXT",
        "float": "NUMERIC(12, 2)",
        "decimal": "NUMERIC(12, 2)",
        "bool": "BOOLEAN",
        "boolean": "BOOLEAN",
        "timestamp": "TIMESTAMPTZ",
        "datetime": "TIMESTAMPTZ",
        "json": "JSONB",
        "uuid": "UUID",
    }

    @classmethod
    def design_table(
        cls,
        table_name: str,
        fields: Dict[str, str],
        dialect: str = "mysql",
        include_timestamps: bool = True,
        include_soft_delete: bool = False,
    ) -> TableDef:
        type_map = cls.TYPE_MAP_PGSQL if dialect.lower() == "postgres" else cls.TYPE_MAP_MYSQL
        table = TableDef(name=table_name.lower())

        # Primary Key
        if dialect.lower() == "postgres":
            table.columns.append(ColumnDef(name="id", col_type="BIGSERIAL", is_primary=True))
        else:
            table.columns.append(
                ColumnDef(
                    name="id",
                    col_type="BIGINT UNSIGNED",
                    auto_increment=True,
                    is_primary=True,
                )
            )

        # Custom Fields
        for name, ftype in fields.items():
            lower_type = ftype.lower()
            is_fk = False
            fk_ref = None

            if name.endswith("_id") and name != "id":
                is_fk = True
                target_table = name[:-3] + "s"
                fk_ref = f"{target_table}(id)"
                sql_type = "BIGINT UNSIGNED" if dialect.lower() == "mysql" else "BIGINT"
                table.indexes.append(f"idx_{table.name}_{name} ({name})")
            else:
                sql_type = type_map.get(lower_type, "VARCHAR(255)")

            is_unique = "unique" in lower_type or name in ("email", "username", "slug")
            nullable = "nullable" in lower_type

            table.columns.append(
                ColumnDef(
                    name=name,
                    col_type=sql_type,
                    nullable=nullable,
                    is_unique=is_unique,
                    foreign_key=fk_ref,
                )
            )

        # Timestamps
        if include_timestamps:
            if dialect.lower() == "postgres":
                table.columns.append(ColumnDef(name="created_at", col_type="TIMESTAMPTZ", default="CURRENT_TIMESTAMP"))
                table.columns.append(ColumnDef(name="updated_at", col_type="TIMESTAMPTZ", default="CURRENT_TIMESTAMP"))
            else:
                table.columns.append(
                    ColumnDef(
                        name="created_at",
                        col_type="TIMESTAMP",
                        default="CURRENT_TIMESTAMP",
                    )
                )
                table.columns.append(
                    ColumnDef(
                        name="updated_at",
                        col_type="TIMESTAMP",
                        default="CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
                    )
                )

        if include_soft_delete:
            table.columns.append(
                ColumnDef(
                    name="deleted_at",
                    col_type="TIMESTAMP" if dialect.lower() == "mysql" else "TIMESTAMPTZ",
                    nullable=True,
                )
            )

        return table

    @classmethod
    def generate_ddl(cls, table: TableDef, dialect: str = "mysql") -> str:
        lines = []
        is_mysql = dialect.lower() == "mysql"
        quote = "`" if is_mysql else '"'

        lines.append(f"CREATE TABLE IF NOT EXISTS {quote}{table.name}{quote} (")

        col_defs = []
        fks = []

        for col in table.columns:
            parts = [f"  {quote}{col.name}{quote}", col.col_type]
            if col.auto_increment and is_mysql:
                parts.append("AUTO_INCREMENT")
            if not col.nullable:
                parts.append("NOT NULL")
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            if col.is_unique:
                parts.append("UNIQUE")
            if col.is_primary:
                parts.append("PRIMARY KEY")
            col_defs.append(" ".join(parts))

            if col.foreign_key:
                ref_table, ref_col = col.foreign_key.split("(")
                ref_col = ref_col.rstrip(")")
                fks.append(
                    f"  CONSTRAINT {quote}fk_{table.name}_{col.name}{quote} FOREIGN KEY ({quote}{col.name}{quote}) "
                    f"REFERENCES {quote}{ref_table}{quote} ({quote}{ref_col}{quote}) ON DELETE CASCADE"
                )

        all_clauses = col_defs + fks
        lines.append(",\n".join(all_clauses))

        if is_mysql:
            lines.append(f") ENGINE={table.engine} DEFAULT CHARSET={table.charset} COLLATE={table.collation};")
        else:
            lines.append(");")

        # Indexes
        for idx in table.indexes:
            idx_name = idx.split()[0]
            col_part = idx.split("(", 1)[1].rstrip(")")
            lines.append(f"CREATE INDEX IF NOT EXISTS {quote}{idx_name}{quote} ON {quote}{table.name}{quote} ({col_part});")

        return "\n".join(lines)
