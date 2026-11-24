import os

import pytest
from sqlalchemy import create_engine

engine = create_engine(os.environ["DATABASE_URL"])


@pytest.fixture
def conn():
    """テストごとにトランザクションを開き、終わったらロールバックする。
    テストで追加・変更・削除したデータは残らず、開発用のデータベースはそのまま"""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
