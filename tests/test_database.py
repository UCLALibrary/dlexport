import os
import unittest

import psycopg

from dlexport import DLExport, DLExportErrorCode, DLExportException


@unittest.skipUnless(
    os.environ.get("DLEXPORT_DB_HOST") and os.environ.get("DLEXPORT_DB_NAME"),
    "Database integration tests require the local Compose database.",
)
class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = DLExport()
        self.database = os.environ["DLEXPORT_DB_NAME"]

    def test_connect_to_db_returns_connection(self) -> None:
        with self.exporter.connect_to_db(self.database) as connection:
            self.assertIsInstance(connection, psycopg.Connection)

    def test_connect_to_db_rejects_unconfigured_database(self) -> None:
        with self.assertRaises(DLExportException):
            self.exporter.connect_to_db("not_configured")

    def test_get_db_collections_returns_collection_names(self) -> None:
        collections = self.exporter.get_db_collections(self.database)

        self.assertTrue(collections)
        self.assertTrue(any(collection == "huxle" for _, collection in collections))

    def test_is_collection_in_db(self) -> None:
        self.assertTrue(self.exporter.is_collection_in_db("huxle", self.database))
        self.assertFalse(self.exporter.is_collection_in_db("not_a_collection", self.database))

    def test_invalid_db_raises_message_and_code(self) -> None:
        with self.assertRaises(DLExportException) as raised:
            self.exporter.get_metadata("invalid", "collection")

        self.assertEqual(raised.exception.code, DLExportErrorCode.INVALID_DATABASE)
        self.assertEqual(str(raised.exception), "Invalid database name.")


if __name__ == "__main__":
    unittest.main()
