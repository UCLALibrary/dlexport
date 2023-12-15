from dlexport import *
import unittest


class DlexportTest(unittest.TestCase):
    def setUp(self):
        self.exporter = Dlexport("db-secrets.json")

        self.invalidDb = [
            "",
            "lit108",
            0,
            1.0,
            [],
            ["lit106"],
            {},
            {"lit106": ""},
            (),
            ("lit106",),
        ]

        # TODO: read these from secrets
        self.validDb = ["lit106", "lit107"]

        self.invalidQuery = [
            "",
            "user",
            0,
            1.0,
            [],
            ["metadata"],
            {},
            {"metadata": ""},
            (),
            ("metadata",),
        ]

        # TODO: read these from secrets
        self.validQuery = ["metadata", "collections"]

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
        for db in self.validDb:
            conn = self.exporter.connectToDb(db)
            self.assertTrue(type(conn) is cx_Oracle.Connection)
            conn.close()

    def test_getDbQuery(self):
        # no arguments

        # one argument

        # invalid arguments
        for db in self.invalidDb:
            with self.assertRaises(DlexportException) as e:
                self.exporter.getDbQuery(db, self.validQuery[0])

            self.assertEqual(e.exception.err, ERR_INVALID_DATABASE)

        for query in self.invalidQuery:
            with self.assertRaises(DlexportException) as e:
                self.exporter.getDbQuery(self.validDb[0], query)

            self.assertEqual(e.exception.err, ERR_INVALID_QUERY)

        # valid arguments
        for db in self.validDb:
            for query in self.validQuery:
                self.assertTrue(type(self.exporter.getDbQuery(db, query)) is str)

    def test_getDbCollections(self):
        pass

    def test_getDatabases(self):
        pass

    def test_isCollectionInDb(self):
        for c in ["apam", "huxle"]:
            # valid db
            self.assertTrue(self.exporter.isCollectionInDb(c, "lit106"))

            # invalid db
            with self.assertRaises(DlexportException) as e:
                invalidDb = "lit108"
                assert not self.exporter.isDb(invalidDb), invalidDb + " is valid!"
                self.exporter.isCollectionInDb(c, invalidDb)

        for c in self.invalidCollection:
            self.assertFalse(self.exporter.isCollectionInDb(c, "lit106"))

    def test_getMetadata(self):
        pass

    def test_toJson(self):
        pass

    def test_toCsv(self):
        pass


if __name__ == "__main__":
    unittest.main()
