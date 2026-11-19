"""Nemr DB Architect Core Package (v3.0.0)."""

__version__ = "3.0.0"

from core.schema_designer import SchemaDesigner, TableDef, ColumnDef
from core.query_optimizer import QueryOptimizer, IndexRecommendation
from core.migration_generator import MigrationGenerator
from core.erd_analyzer import ErdAnalyzer
from core.seeder_generator import SeederGenerator
from core.schema_differ import SchemaDiffer
from core.pdo_repository_gen import PdoRepositoryGenerator

__all__ = [
    "__version__",
    "SchemaDesigner",
    "TableDef",
    "ColumnDef",
    "QueryOptimizer",
    "IndexRecommendation",
    "MigrationGenerator",
    "ErdAnalyzer",
    "SeederGenerator",
    "SchemaDiffer",
    "PdoRepositoryGenerator",
]
