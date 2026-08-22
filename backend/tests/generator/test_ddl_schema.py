import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "app" / "generator"))

from schema.ddl import get_ddl


def test_get_ddl_defaults_to_public_schema():
    ddl = get_ddl("products")
    assert "CREATE TABLE IF NOT EXISTS public.products" in ddl


def test_get_ddl_qualifies_with_given_schema():
    ddl = get_ddl("products", schema="demo")
    assert "CREATE TABLE IF NOT EXISTS demo.products" in ddl
    assert "CREATE TABLE IF NOT EXISTS products (" not in ddl


def test_get_ddl_only_replaces_first_occurrence():
    ddl = get_ddl("customers", schema="demo")
    assert ddl.count("demo.customers") == 1
