#!/usr/bin/env python3
"""Unit tests for Nemr DB Architect."""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.schema_designer import SchemaDesigner
from core.query_optimizer import QueryOptimizer
from core.migration_generator import MigrationGenerator


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


if __name__ == "__main__":
    unittest.main()
