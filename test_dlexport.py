import os
import unittest

import psycopg

from dlexport import Dlexport, DlexportException


class DlexportTest(unittest.TestCase):
    def setUp(self):
        self.exporter = Dlexport()
        self.database = os.environ["DLEXPORT_DB_NAME"]

        self.invalidDb = ["", "lit108", 0, 1.0, [], ["lit106"], {}, {"lit106": ""}, (), ("lit106",)]

        self.invalidCollection = [
            "",
            "markmatney",
            0,
            1.0,
            [],
            ["apam"],
            {},
            {"apam": ""},
            (),
            ("apam",),
        ]

    def test_connectToDb(self):

        # no arguments
        with self.assertRaises(TypeError) as e:
            self.exporter.connectToDb()

        # invalid argument
        for db in self.invalidDb:
            with self.assertRaises(DlexportException) as e:
                conn = self.exporter.connectToDb(db)

                # should never reach this point
                conn.close()

        # valid argument
        conn = self.exporter.connectToDb(self.database)
        self.assertIsInstance(conn, psycopg.Connection)
        conn.close()

    def test_getDbCollections(self):
        pass

    def test_getDatabases(self):
        pass

    def test_isCollectionInDb(self):
        for c in ["apam", "huxle"]:
            # valid db
            self.assertTrue(self.exporter.isCollectionInDb(c, self.database))

            # invalid db
            with self.assertRaises(DlexportException) as e:
                invalidDb = "lit108"
                assert not self.exporter.isDb(invalidDb), invalidDb + " is valid!"
                self.exporter.isCollectionInDb(c, invalidDb)

        for c in self.invalidCollection:
            self.assertFalse(self.exporter.isCollectionInDb(c, self.database))

    def test_getMetadata(self):
        pass

    def test_toJson(self):
        pass

    def test_toCsv(self):
        pass


if __name__ == "__main__":
    unittest.main()
