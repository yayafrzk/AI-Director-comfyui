from sqlalchemy import inspect, text

from app.db.init_db import init_db
from app.db.session import create_engine_for_path


def test_init_db_adds_megapixels_to_existing_sqlite_scenes_table(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "legacy-scenes.sqlite")
    try:
        with database_engine.begin() as connection:
            connection.execute(text("CREATE TABLE scenes (id TEXT PRIMARY KEY)"))
            connection.execute(text("INSERT INTO scenes (id) VALUES ('legacy-scene')"))

        init_db(database_engine)
        columns = {column["name"] for column in inspect(database_engine).get_columns("scenes")}
        assert "megapixels" in columns

        with database_engine.connect() as connection:
            megapixels = connection.scalar(
                text("SELECT megapixels FROM scenes WHERE id = 'legacy-scene'")
            )
        assert megapixels == 0.6

        init_db(database_engine)
        repeated_columns = [
            column["name"] for column in inspect(database_engine).get_columns("scenes")
        ]
        assert repeated_columns.count("megapixels") == 1
    finally:
        database_engine.dispose()


def test_init_db_creates_megapixels_for_new_sqlite_database(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "new-scenes.sqlite")
    try:
        init_db(database_engine)
        columns = {column["name"] for column in inspect(database_engine).get_columns("scenes")}
        assert "megapixels" in columns
    finally:
        database_engine.dispose()
