import json
import unittest

from dlexport import (
    DLExport,
    clean,
    find_ark,
    name_child_pages,
)


class HelperTests(unittest.TestCase):
    def test_clean_removes_newline_characters(self) -> None:
        self.assertEqual(clean("line\r\nbreak\n"), "linebreak")

    def test_find_ark_matches_file_and_skips_work_and_collection(self) -> None:
        metadata = {
            "work": {"Object Type": "Work", "File Name": "image.tif"},
            "collection": {"Object Type": "Collection", "File Name": "image.tif"},
            "page": {"Object Type": "Page", "File Name": "image.tif"},
        }

        self.assertEqual(find_ark(metadata, "image.tif"), "page")
        self.assertIsNone(find_ark(metadata, "missing.tif"))

    def test_name_child_pages_applies_selected_names(self) -> None:
        metadata = {
            "page-1": {
                "Parent ARK": "parent",
                "Item Sequence": "1",
                "Title": "old title",
            },
            "page-2": {
                "Parent ARK": "parent",
                "Item Sequence": "2",
                "Title": "old title",
            },
            "other": {"Parent ARK": "elsewhere", "Item Sequence": "1"},
        }

        result = name_child_pages(["a.tif", "b.tif"], "front-back", metadata, "parent")

        self.assertIs(result, metadata)
        self.assertEqual(result["page-1"]["Title"], "Front")
        self.assertEqual(result["page-2"]["Title"], "Back")
        self.assertNotIn("Title", result["other"])

    def test_name_child_pages_leaves_items_with_more_than_two_files_unchanged(self) -> None:
        metadata = {"page": {"Parent ARK": "parent", "Item Sequence": "1"}}

        name_child_pages(["a.tif"], "page-number", metadata, "parent")

        self.assertNotIn("Title", metadata["page"])


class ExporterOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = DLExport()

    def test_to_csv_serializes_fixture_metadata(self) -> None:
        self.exporter.csv_headers = ["Item ARK", "Title", "Description"]
        self.exporter.metadata = {
            "ark:/1": {
                "Item ARK": "ark:/1",
                "Title": "First\nitem",
                "Description": None,
            }
        }

        output = self.exporter.to_csv()

        self.assertEqual(
            output,
            '"Item ARK","Title","Description"\r\n"ark:/1","Firstitem",""\r\n',
        )

    def test_to_json_serializes_fixture_metadata(self) -> None:
        self.exporter.metadata = {"ark:/1": {"Title": "First item"}}

        self.assertEqual(json.loads(self.exporter.to_json()), self.exporter.metadata)


if __name__ == "__main__":
    unittest.main()
