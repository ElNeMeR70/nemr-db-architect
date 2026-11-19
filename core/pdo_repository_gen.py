"""
Nemr DB Architect - PHP 8.3 Strict PDO Repository & Readonly DTO Generator (v3.0.0)
Emits immutable readonly entity records and SQLi-immune parameterized PDO CRUD repositories.
"""

from __future__ import annotations
from typing import Dict


class PdoRepositoryGenerator:
    """Generates PHP 8.3 readonly record DTOs and prepared-statement PDO repositories."""

    TYPE_MAP = {
        "int": "int",
        "integer": "int",
        "bigint": "int",
        "float": "float",
        "decimal": "float",
        "bool": "bool",
        "boolean": "bool",
    }

    @classmethod
    def _singular_entity(cls, table_name: str) -> str:
        clean = table_name.strip().lower()
        if clean.endswith("ies") and len(clean) > 3:
            clean = clean[:-3] + "y"
        elif clean.endswith("s") and len(clean) > 2:
            clean = clean[:-1]
        return "".join(part.capitalize() for part in clean.split("_"))

    @classmethod
    def generate_repository(
        cls,
        table_name: str,
        fields: Dict[str, str],
        namespace: str = "App\\Repositories",
    ) -> str:
        entity = cls._singular_entity(table_name)
        table = table_name.lower()

        ctor_params = []
        from_args = []
        insert_cols = []
        insert_params = []
        insert_binds = []
        update_sets = []
        update_binds = []

        for fname, ftype in fields.items():
            php_t = cls.TYPE_MAP.get(ftype.lower(), "string")
            ctor_params.append(f"        public {php_t} ${fname},")
            cast = f"({php_t})" if php_t in ("int", "float", "bool") else "(string)"
            default_expr = "0" if php_t in ("int", "float") else ("false" if php_t == "bool" else "''")
            from_args.append(f"            {fname}: {cast}($row['{fname}'] ?? {default_expr}),")
            insert_cols.append(f"`{fname}`")
            insert_params.append(f":{fname}")
            insert_binds.append(f"            ':{fname}' => $data['{fname}'] ?? null,")
            update_sets.append(f"`{fname}` = :{fname}")
            update_binds.append(f"            ':{fname}' => $data['{fname}'] ?? null,")

        return f"""<?php
declare(strict_types=1);

namespace {namespace};

use PDO;
use Throwable;

/**
 * Immutable PHP 8.3 Record DTO for `{table}`
 */
readonly class {entity}Record
{{
    public function __construct(
        public int $id,
{chr(10).join(ctor_params)}
        public string $createdAt = '',
    ) {{}}

    public static function fromRow(array $row): self
    {{
        return new self(
            id: (int)($row['id'] ?? 0),
{chr(10).join(from_args)}
            createdAt: (string)($row['created_at'] ?? ''),
        );
    }}
}}

/**
 * Parameterized PDO Repository for `{table}` (100% SQLi Proof)
 */
class {entity}Repository
{{
    public function __construct(protected PDO $pdo) {{}}

    public function findById(int $id): ?{entity}Record
    {{
        $stmt = $this->pdo->prepare('SELECT * FROM `{table}` WHERE `id` = :id LIMIT 1');
        $stmt->execute([':id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        return $row ? {entity}Record::fromRow($row) : null;
    }}

    /**
     * @return {entity}Record[]
     */
    public function paginate(int $limit = 25, int $offset = 0): array
    {{
        $stmt = $this->pdo->prepare('SELECT * FROM `{table}` ORDER BY `id` DESC LIMIT :lim OFFSET :off');
        $stmt->bindValue(':lim', max(1, $limit), PDO::PARAM_INT);
        $stmt->bindValue(':off', max(0, $offset), PDO::PARAM_INT);
        $stmt->execute();
        return array_map(fn(array $r) => {entity}Record::fromRow($r), $stmt->fetchAll(PDO::FETCH_ASSOC));
    }}

    public function insert(array $data): int
    {{
        $stmt = $this->pdo->prepare(
            'INSERT INTO `{table}` ({", ".join(insert_cols)}) VALUES ({", ".join(insert_params)})'
        );
        $stmt->execute([
{chr(10).join(insert_binds)}
        ]);
        return (int)$this->pdo->lastInsertId();
    }}

    public function update(int $id, array $data): bool
    {{
        $stmt = $this->pdo->prepare(
            'UPDATE `{table}` SET {", ".join(update_sets)} WHERE `id` = :id'
        );
        return $stmt->execute([
            ':id' => $id,
{chr(10).join(update_binds)}
        ]);
    }}

    public function delete(int $id): bool
    {{
        $stmt = $this->pdo->prepare('DELETE FROM `{table}` WHERE `id` = :id');
        return $stmt->execute([':id' => $id]);
    }}

    public function inTransaction(callable $callback): mixed
    {{
        $this->pdo->beginTransaction();
        try {{
            $result = $callback($this);
            $this->pdo->commit();
            return $result;
        }} catch (Throwable $e) {{
            $this->pdo->rollBack();
            throw $e;
        }}
    }}
}}
"""
