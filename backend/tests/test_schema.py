import pytest
from sqlalchemy import text

from app.main import check_schema


def test_current_schema_passes(conn):
    check_schema(conn)


def test_missing_sessions_table_fails_with_reset_message(conn):
    # 空のスキーマを検索先にして、sessions テーブルがない古いデータベースのふりをする
    conn.execute(text("CREATE SCHEMA old_db"))
    conn.execute(text("SET LOCAL search_path TO old_db"))
    with pytest.raises(RuntimeError, match="make reset"):
        check_schema(conn)


@pytest.mark.parametrize("table, column", [
    ("users", "role"),
    ("users", "is_active"),
    ("task_type", "is_active"),
])
def test_missing_column_fails_with_reset_message(conn, table, column):
    # ロールバックされるので、実際の列は消えない
    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
    with pytest.raises(RuntimeError, match="make reset"):
        check_schema(conn)
