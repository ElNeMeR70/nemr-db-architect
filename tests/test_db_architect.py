#!/usr/bin/env python3
"""Unit tests for Nemr DB Architect v2.0.0."""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.schema_designer import SchemaDesigner
from core.query_optimizer import QueryOptimizer
from core.migration_generator import MigrationGenerator
from core.erd_analyzer import ErdAnalyzer
from core.seeder_generator import SeederGenerator
from core.schema_differ import SchemaDiffer
from core.pdo_repository_gen import PdoRepositoryGenerator


class TestDbArchitect(unittest.TestCase):
    def test_schema_designer_mysql(self):
        tbl = SchemaDesigner.design_table("products", {"title": "string", "price": "decimal", "user_id": "int"})
        self.assertEqual(tbl.name, "products")
        ddl = SchemaDesigner.generate_ddl(tbl, dialect="mysql")
        self.assertIn("CREATE TABLE IF NOT EXISTS `products`", ddl)
        self.assertIn("`id` BIGINT UNSIGNED AUTO_INCREMENT", ddl)
        self.assertIn("`price` DECIMAL(12, 2)", ddl)
        self.assertIn("FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)", ddl)

    def test_schema_designer_postgres(self):
        tbl = SchemaDesigner.design_table("invoices", {"amount": "float", "customer_email": "string"}, dialect="postgres")
        ddl = SchemaDesigner.generate_ddl(tbl, dialect="postgres")
        self.assertIn('CREATE TABLE IF NOT EXISTS "invoices"', ddl)
        self.assertIn('"id" BIGSERIAL NOT NULL PRIMARY KEY', ddl)

    def test_query_optimizer_recommends_composite_index(self):
        sql = "SELECT id, total FROM orders WHERE status = 'pending' AND user_id = 45 ORDER BY created_at DESC"
        res = QueryOptimizer.analyze_query(sql)
        self.assertEqual(res["main_table"], "orders")
        self.assertIn("status", res["where_columns"])
        self.assertIn("user_id", res["where_columns"])
        self.assertGreaterEqual(len(res["recommendations"]), 1)
        rec = res["recommendations"][0]
        self.assertIn("CREATE INDEX", rec.sql)

    def test_query_optimizer_catches_leading_wildcard(self):
        sql = "SELECT * FROM users WHERE name LIKE '%john%'"
        res = QueryOptimizer.analyze_query(sql)
        self.assertTrue(any("Leading wildcard" in w for w in res["warnings"]))
        self.assertTrue(any("SELECT *" in w for w in res["warnings"]))

    def test_migration_generator(self):
        res = MigrationGenerator.generate_migration("add_status_to_users", "ALTER TABLE users ADD status VARCHAR(50);", "ALTER TABLE users DROP COLUMN status;", format_type="sql")
        fname = list(res.keys())[0]
        self.assertTrue(fname.endswith(".sql"))
        self.assertIn("START TRANSACTION;", res[fname])
        self.assertIn("ALTER TABLE users ADD status", res[fname])

    # v2.0.0 Tests
    def test_erd_analyzer_audit_schema(self):
        bad_sql = """
        CREATE TABLE orders (
            user_id BIGINT NOT NULL,
            total FLOAT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
        """
        findings = ErdAnalyzer.audit_schema(bad_sql)
        issues = {f["issue"] for f in findings}
        self.assertIn("MISSING_PRIMARY_KEY", issues)
        self.assertIn("MISSING_FK_INDEX", issues)
        self.assertIn("FLOAT_CURRENCY_PRECISION", issues)
        self.assertIn("LEGACY_ENGINE_OR_CHARSET", issues)

    def test_erd_analyzer_mermaid_diagram(self):
        sql = """
        CREATE TABLE users (
            id BIGINT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL
        );
        CREATE TABLE invoices (
            id BIGINT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
        erd = ErdAnalyzer.generate_mermaid_erd(sql)
        self.assertIn("erDiagram", erd)
        self.assertIn("USERS {", erd)
        self.assertIn("INVOICES {", erd)
        self.assertIn('USERS ||--o{ INVOICES : "user_id"', erd)

    def test_query_optimizer_esr_join_and_sargable(self):
        sql = (
            "SELECT o.id, o.total FROM orders o "
            "INNER JOIN users u ON o.user_id = u.id "
            "WHERE o.created_at > '2026-01-01' AND o.status = 'paid' AND YEAR(o.created_at) = 2026 "
            "ORDER BY o.total DESC"
        )
        res = QueryOptimizer.analyze_query(sql)
        # ESR order: status (=) before total (ORDER BY) before created_at (>)
        self.assertEqual(res["esr_order"], ["status", "total", "created_at"])
        self.assertGreaterEqual(len(res["join_recommendations"]), 1)
        self.assertEqual(res["join_recommendations"][0].columns, ["user_id"])
        self.assertTrue(any("2026-01-01" in rw for rw in res["rewrites"]))

    def test_seeder_generator(self):
        seed_mysql = SeederGenerator.generate_sql_seed(
            "orders", {"email": "string", "amount": "decimal", "is_paid": "bool", "status": "string"}, rows=3, dialect="mysql"
        )
        self.assertIn("INSERT INTO `orders`", seed_mysql)
        self.assertIn("user1@elnemer-ai.com", seed_mysql)
        self.assertIn("user3@elnemer-ai.com", seed_mysql)

        seed_pg = SeederGenerator.generate_sql_seed(
            "orders", {"is_paid": "bool"}, rows=2, dialect="postgres"
        )
        self.assertIn('INSERT INTO "orders"', seed_pg)
        self.assertIn("TRUE", seed_pg)

    # v3.0.0 Tests
    def test_schema_differ_table_and_columns(self):
        old_sql = """
        CREATE TABLE users (
            id BIGINT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            legacy_col INT NOT NULL
        );
        CREATE TABLE temp_logs (id INT PRIMARY KEY);
        """
        new_sql = """
        CREATE TABLE users (
            id BIGINT PRIMARY KEY,
            email VARCHAR(320) NOT NULL,
            role VARCHAR(50) NOT NULL
        );
        CREATE TABLE invoices (
            id BIGINT PRIMARY KEY,
            amount DECIMAL(12,2) NOT NULL
        );
        """
        diff = SchemaDiffer.diff_schemas(old_sql, new_sql, dialect="mysql")
        self.assertTrue(diff["has_changes"])
        self.assertIn("CREATE TABLE `invoices`", diff["up_sql"])
        self.assertIn("DROP TABLE IF EXISTS `temp_logs`", diff["up_sql"])
        self.assertIn("ADD COLUMN `role` VARCHAR(50)", diff["up_sql"])
        self.assertIn("MODIFY COLUMN `email` VARCHAR(320)", diff["up_sql"])
        self.assertIn("DROP COLUMN `legacy_col`", diff["up_sql"])
        self.assertIn("DROP TABLE IF EXISTS `invoices`", diff["down_sql"])

    def test_schema_differ_postgres_alter(self):
        old_sql = 'CREATE TABLE items ("id" BIGINT PRIMARY KEY, "qty" INT NOT NULL);'
        new_sql = 'CREATE TABLE items ("id" BIGINT PRIMARY KEY, "qty" BIGINT NOT NULL);'
        diff = SchemaDiffer.diff_schemas(old_sql, new_sql, dialect="postgres")
        self.assertTrue(diff["has_changes"])
        self.assertIn('ALTER TABLE "items" ALTER COLUMN "qty" TYPE BIGINT;', diff["up_sql"])
        self.assertIn('ALTER TABLE "items" ALTER COLUMN "qty" TYPE INT;', diff["down_sql"])

    def test_pdo_repository_generator(self):
        php_repo = PdoRepositoryGenerator.generate_repository(
            "orders", {"user_id": "int", "total": "decimal", "is_paid": "bool"}
        )
        self.assertIn("readonly class OrderRecord", php_repo)
        self.assertIn("class OrderRepository", php_repo)
        self.assertIn("public function findById(int $id): ?OrderRecord", php_repo)
        self.assertIn("public function inTransaction(callable $callback): mixed", php_repo)
        self.assertIn("$this->pdo->prepare(", php_repo)


if __name__ == "__main__":
    unittest.main()
