"""
Nemr DB Architect - Zero-Downtime Migration Generator
Generates atomic UP / DOWN database migrations with transaction wrappers and safety checks.
"""

from __future__ import annotations
import datetime
from pathlib import Path
from typing import Dict, Any


class MigrationGenerator:
    """Generates production-grade migration scripts with rollback capability."""

    @classmethod
    def generate_migration(
        cls,
        name: str,
        up_sql: str,
        down_sql: str,
        format_type: str = "sql"
    ) -> Dict[str, str]:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = name.lower().replace(" ", "_").replace("-", "_")
        filename_base = f"{timestamp}_{slug}"

        if format_type == "php":
            content = f"""<?php
declare(strict_types=1);

/**
 * Migration: {name}
 * Generated: {datetime.datetime.now().isoformat()}
 */
class Migration_{slug}
{{
    public function up(PDO $pdo): void
    {{
        $pdo->beginTransaction();
        try {{
            $pdo->exec(<<<'SQL'
{up_sql.strip()}
SQL
            );
            $pdo->commit();
        }} catch (Throwable $e) {{
            $pdo->rollBack();
            throw $e;
        }}
    }}

    public function down(PDO $pdo): void
    {{
        $pdo->beginTransaction();
        try {{
            $pdo->exec(<<<'SQL'
{down_sql.strip()}
SQL
            );
            $pdo->commit();
        }} catch (Throwable $e) {{
            $pdo->rollBack();
            throw $e;
        }}
    }}
}}
"""
            return {f"{filename_base}.php": content}

        # Default raw SQL format
        sql_content = f"""-- ========================================================
-- Migration: {name}
-- Generated: {datetime.datetime.now().isoformat()}
-- ========================================================

-- >>> UP >>>
START TRANSACTION;

{up_sql.strip()}

COMMIT;

-- >>> DOWN >>>
-- To rollback, execute:
-- START TRANSACTION;
-- {down_sql.strip()}
-- COMMIT;
"""
        return {f"{filename_base}.sql": sql_content}
