"""Export project metadata from DLCS to CSV or JSON format."""

import csv
import io
import os
import random
import re
import urllib.parse
from datetime import date, datetime
from enum import IntEnum, StrEnum
from json import dumps
from pathlib import Path
from typing import Any, Iterator, LiteralString, Mapping

import psycopg
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from noid import mint

####################
# region Queries
####################
METADATA_QUERY = """
SELECT 
    c.project_title, 
    b.item_ark, 
    b.item_sequence,
    b.statusid_fk,
    q.status,
    a.desc_term_label, 
    a.core_desc_term, 
    a.qualifier_label, 
    a.text_value, 
    parent_join.item_ark AS parent_ark, 
    v_ot.object_type, 
    CASE
        WHEN p_ot.object_type IS NOT NULL
        THEN p_ot.object_type
        ELSE ''
    END AS parent_obj_type, 
    cf.file_name, cf.file_location
-- a.desc_term_label, a.qualifier_label, parent_join.item_ark as parent_ark,
-- b.item_ark, v_ot.object_type, a.text_value as tv
FROM 
    (SELECT 
        dv.divid_fk AS item_id, 
        dv.projectid_fk AS project_id, 
        cdt.desc_term AS core_desc_term, 
        cdt.core_desc_termid_pk AS core_desc_termid_id, 
        dt.term_label AS desc_term_label, 
        dt.desc_termid_pk AS desc_termid_id, 
        v_qual.qual_text AS qualifier_label,
        CASE 
            WHEN dv.desc_cvid_fk IS NOT NULL 
            THEN ctrl_values.ctrl_val_text 
            ELSE dv.desc_value 
        END AS text_value, 
        dv.desc_cvid_fk AS desc_control_values_id, 
        dv.desc_qualifierid_fk AS desc_qualifiers_id, 
        v_qual.qid AS core_desc_qualifiers_id, 
        ctrl_values.core_desc_cvid_pk AS core_desc_control_values_id 
    FROM desc_values dv
    INNER JOIN desc_terms dt ON dv.desc_termid_fk = dt.desc_termid_pk
    INNER JOIN core_desc_terms cdt ON dt.core_desc_termid_fk = cdt.CORE_DESC_TERMID_PK
    LEFT OUTER JOIN
        (SELECT DISTINCT 
            dq.core_desc_qualifierid_fk AS qid, 
            cdq.desc_qualifier AS qual_text, 
            dq.desc_qualifierid_pk AS desc_qual_pk 
        FROM desc_qualifiers dq, core_desc_qualifiers cdq 
        WHERE dq.CORE_DESC_QUALIFIERID_FK = cdq.core_desc_qualifierid_pk ) v_qual
    ON dv.desc_qualifierid_fk = v_qual.desc_qual_pk
    LEFT OUTER JOIN
        (SELECT DISTINCT 
            cdcv.core_desc_cv AS ctrl_val_text, 
            dcv.desc_cvid_pk, 
            cdcv.core_desc_cvid_pk 
        FROM core_desc_control_values cdcv, desc_control_values dcv 
        WHERE cdcv.core_desc_cvid_pk = dcv.core_desc_cvid_fk ) ctrl_values 
    ON dv.desc_cvid_fk = ctrl_values.desc_cvid_pk
    ) a 
INNER JOIN project_items b 
ON a.item_id = b.divid_pk 
INNER JOIN projects c 
ON b.projectid_fk = c.projectid_pk 
LEFT OUTER JOIN qa_status q
ON b.statusid_fk = q.statusid_pk
INNER JOIN 
    (SELECT objectid_pk, object_label, object_type
    FROM dl_objects, dl_object_types
    WHERE object_typeid_fk = object_typeid_pk
    ) v_ot
ON v_ot.objectid_pk = b.objectid_fk 
LEFT OUTER JOIN content_files cf
ON b.divid_pk = cf.divid_fk 
AND cf.file_use = 'Master'
LEFT OUTER JOIN project_items parent_join
ON b.parent_divid = parent_join.divid_pk
LEFT OUTER JOIN 
    (SELECT objectid_pk, object_label, object_type
    FROM dl_objects, dl_object_types
    WHERE object_typeid_fk = object_typeid_pk
    ) p_ot
ON p_ot.objectid_pk = parent_join.objectid_fk
WHERE project_id IN 
    (SELECT projectid_pk 
    FROM projects 
    WHERE webapp_name = %(collection)s )
"""


COLLECTIONS_QUERY = """
SELECT project_title, webapp_name 
FROM projects 
ORDER BY project_title
"""


THUMBNAIL_QUERY = """
SELECT pi.item_ark, cf.file_name, cf.file_location 
FROM projects p 
    INNER JOIN project_items pi ON p.projectid_pk = pi.projectid_fk 
    INNER JOIN content_files cf ON pi.divid_pk = cf.divid_fk 
WHERE cf.file_use = 'Thumbnail' 
AND p.webapp_name = %(collection)s
ORDER BY pi.item_ark
"""


MASTER_IMG_QUERY = """
SELECT pi.item_ark, cf.file_name, cf.file_location 
FROM projects p 
INNER JOIN project_items pi ON p.projectid_pk = pi.projectid_fk 
INNER JOIN content_files cf ON pi.divid_pk = cf.divid_fk 
WHERE cf.file_use = 'Master' 
AND p.webapp_name = %(collection)s
ORDER BY pi.item_ark
"""


EDITED_ITEMS_QUERY = """
SELECT 
    project_items.create_date,
    project_items.last_edit_date,
    project_items.item_ark,
    project_items.node_title,
    project_items.modified_by,
    project_items.created_by,
    projects.project_title
FROM project_items, projects
WHERE projects.projectid_pk = project_items.projectid_fk 
    AND project_items.last_edit_date >= CAST(%(start_date)s AS DATE)
    AND project_items.last_edit_date <= CAST(%(end_date)s AS DATE)
ORDER BY last_edit_date DESC
"""
# endregion Queries


####################
# region Helpers
def clean(dirty: str) -> str:
    """Strip newline and carriage-return characters from a string."""
    return dirty.replace("\r", "").replace("\n", "")


def find_ark(metadata_dict: Mapping[str, Mapping[str, Any]], file_name: str) -> str | None:
    """Find the item ARK for a matching non-Work, non-Collection file.

    Args:
        metadata_dict: Metadata indexed by item ARK.
        file_name: File name to find.

    Returns:
        The matching item ARK, or None when no item matches.
    """
    for item_ark, item in metadata_dict.items():
        if item.get("Object Type") not in ("Work", "Collection"):
            if item.get("File Name") == file_name:
                return item_ark
    return None


def name_child_pages(
    file_list: list[str],
    page_name: str,
    metadata_dict: dict[str, dict[str, Any]],
    parent: str,
) -> dict[str, dict[str, Any]]:
    """Set titles for the two pages belonging to a parent item.

    Args:
        file_list: Files associated with the parent.
        page_name: Naming convention to use for the two pages.
        metadata_dict: Metadata indexed by item ARK.
        parent: Parent item ARK.

    Returns:
        The updated metadata dictionary.
    """
    page_names = {
        "page-number": ["Page 1", "Page 2"],
        "front-back": ["Front", "Back"],
        "recto-verso": ["Recto", "Verso"],
    }
    if len(file_list) == 2:
        for item in metadata_dict.values():
            if item.get("Parent ARK") == parent:
                item["Title"] = "Title"
                if item.get("Item Sequence") == "1":
                    item["Title"] = page_names[page_name][0]
                elif item.get("Item Sequence") == "2":
                    item["Title"] = page_names[page_name][1]
    return metadata_dict


# endregion Helpers


####################
# region Main DLExport class and exceptions
####################
class DLExportErrorCode(IntEnum):
    """Stable process exit codes for expected export errors."""

    SUCCESS = 0
    INVALID_DATABASE = 1
    INVALID_COLLECTION = 2
    EMPTY_COLLECTION = 3
    INVALID_FILENAME = 4
    UNKNOWN = 5
    INVALID_QUERY = 6


ERROR_MESSAGES = {
    DLExportErrorCode.INVALID_DATABASE: "Invalid database name.",
    DLExportErrorCode.INVALID_COLLECTION: "Invalid collection name.",
    DLExportErrorCode.EMPTY_COLLECTION: "The collection contains no items.",
    DLExportErrorCode.INVALID_FILENAME: "Invalid output file.",
    DLExportErrorCode.UNKNOWN: "An unexpected export error occurred.",
    DLExportErrorCode.INVALID_QUERY: "The database query failed.",
}


class DLExportException(Exception):
    """Represent a user-facing export error and its stable exit code."""

    def __init__(self, code: DLExportErrorCode, message: str | None = None) -> None:
        """Create an export error with a stable code and readable message."""
        self.code = code
        super().__init__(
            message or ERROR_MESSAGES.get(code, ERROR_MESSAGES[DLExportErrorCode.UNKNOWN])
        )


class DLExport:
    """Exporter class."""

    def __init__(self) -> None:
        """Store PostgreSQL connection settings from the environment."""
        self.csv_headers: list[str] = []
        self.metadata: dict[str, dict[str, Any]] = {}
        self.edited_items: list[tuple[Any, ...]] = []
        required_settings = (
            "DLEXPORT_DB_HOST",
            "DLEXPORT_DB_PORT",
            "DLEXPORT_DB_NAME",
            "DLEXPORT_DB_USER",
            "DLEXPORT_DB_PASSWORD",
        )
        missing_settings = [setting for setting in required_settings if setting not in os.environ]
        if missing_settings:
            raise RuntimeError(
                "Missing database configuration environment variables: "
                + ", ".join(missing_settings)
            )

        self._database_host = os.environ["DLEXPORT_DB_HOST"]
        self._database_port = int(os.environ["DLEXPORT_DB_PORT"])
        self._database_name = os.environ["DLEXPORT_DB_NAME"]
        self._database_user = os.environ["DLEXPORT_DB_USER"]
        self._database_password = os.environ["DLEXPORT_DB_PASSWORD"]

    def connect_to_db(self, db: str) -> psycopg.Connection[Any]:
        """Open a connection to the configured PostgreSQL database.

        Args:
            db: Database name to connect to.

        Returns:
            An open PostgreSQL connection.

        Raises:
            DLExportException: If the requested database is not configured.
        """
        if db not in self.get_databases():
            raise DLExportException(DLExportErrorCode.INVALID_DATABASE)

        return psycopg.connect(
            host=self._database_host,
            port=self._database_port,
            dbname=self._database_name,
            user=self._database_user,
            password=self._database_password,
        )

    def _execute_query(
        self, db: str, query: LiteralString, params: Mapping[str, Any] | None = None
    ) -> Iterator[tuple[Any, ...]]:
        """Execute a query and yield its result rows."""
        with self.connect_to_db(db) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                yield from cursor

    def get_db_collections(self, db: str) -> list[list[Any]]:
        """Return the configured database's project titles and collection names.

        Args:
            db: Database name to query.

        Returns:
            Each row contains a project title and its collection name.
        """
        return [[a, b] for a, b in self._execute_query(db, COLLECTIONS_QUERY)]

    def get_databases(self, include_collections: bool = False) -> list[Any]:
        """Return the configured database, optionally with its collections.

        Args:
            include_collections: Include collection rows alongside the database name.

        Returns:
            The configured database name, optionally paired with collection rows.
        """
        db_list = [self._database_name]
        if include_collections:
            return [[name, self.get_db_collections(name)] for name in db_list]
        return db_list

    def is_db(self, db: str) -> bool:
        """Check whether a database name is configured.

        Args:
            db: Database name to check.

        Returns:
            True when the name matches the configured database.
        """
        return db in self.get_databases()

    def is_collection_in_db(self, collection: str, db: str) -> bool:
        """Check whether a collection exists in a database.

        Args:
            collection: Collection name to check.
            db: Database name to query.

        Returns:
            True when the collection exists in the database.
        """
        collections = [item[1] for item in self.get_db_collections(db)]
        return collection in collections

    def get_metadata(
        self,
        db: str | None = None,
        collection: str | None = None,
        thumbnail: str = "first-thumb",
        page_name: str = "page-number",
    ) -> None:
        """Load and organize metadata for a collection.

        Args:
            db: Database name to query.
            collection: Collection name to export.
            thumbnail: File selection rule for generated thumbnails.
            page_name: Page title convention for two-file works.

        Raises:
            DLExportException: If the database or collection is invalid or empty.
        """
        if db is None or db not in self.get_databases():
            raise DLExportException(DLExportErrorCode.INVALID_DATABASE)
        if collection is None or not self.is_collection_in_db(collection, db):
            raise DLExportException(DLExportErrorCode.INVALID_COLLECTION)

        # go thru query results, organize metadata in dictionary keyed by item_ark
        # keep track of all 2nd-tier keys
        # count number of rows in result
        metadata: dict[str, dict[str, Any]] = {}
        csv_headers = [
            "Project Name",
            "Item ARK",
            "Parent ARK",
            "Item Status ID",
            "Item Status",
            "Object Type",
            "File Name",
            "Item Sequence",
            "Duplicate",
            "Delete in Title",
            "Thumbnail",
        ]
        row_count = 0

        for (
            project_title,
            item_ark,
            item_sequence,
            statusid_fk,
            status,
            desc_term_label,
            _core_desc_term,
            qualifier_label,
            text_value,
            parent_ark,
            object_type,
            parent_obj_type,
            _file_name,
            file_location,
        ) in self._execute_query(db, METADATA_QUERY, {"collection": collection}):
            row_count += 1

            # set a variable for metadata dictionary
            # will only have a value if the object type in DLCS is Page
            paginated_object_type = None
            if object_type != "Collection":
                if parent_obj_type == "Collection":
                    object_type = "Work"
                elif object_type == "Page":
                    paginated_object_type = "Page"
                    object_type = "ChildWork"
                else:
                    object_type = "ChildWork"

            # check if we've started accounting for this item yet
            # add ark:/ format to ark string for csv output
            # check if this item has a parent ark because the collection level item will not
            if item_ark not in metadata:
                readable_item_ark = "ark:/" + str(item_ark)
                if parent_ark == None:
                    readable_parent_ark = ""
                else:
                    readable_parent_ark = "ark:/" + str(parent_ark)

                metadata[item_ark] = {
                    "Project Name": project_title,
                    "Item ARK": readable_item_ark,
                    "Parent ARK": readable_parent_ark,
                    "Item Status ID": str(statusid_fk),
                    "Item Status": status,
                    "Object Type": object_type,
                    "Item Sequence": ("" if item_sequence is None else str(item_sequence)),
                    "Pagination": paginated_object_type,
                    "Thumbnail": "",
                }

            # check if in DLCS object_type is "Page"
            # if so, add four new fields for paginated materials
            # add paged value to work row if paginated material
            if metadata[item_ark]["Pagination"] == "Page":
                if "viewingHint" not in csv_headers:
                    csv_headers.extend(
                        ("viewingHint", "Text direction", "Visibility", "IIIF Range")
                    )
                if parent_ark in metadata and metadata[parent_ark]["Object Type"] == "Work":
                    metadata[parent_ark]["viewingHint"] = "paged"

            if qualifier_label in (False, None) or len(qualifier_label) <= 0:
                inner_dict_key = desc_term_label
            else:
                inner_dict_key = "{0}.{1}".format(desc_term_label, qualifier_label)

            # check if we've encountered a new header field
            if inner_dict_key not in csv_headers:
                csv_headers.append(inner_dict_key)
            # check if inner_dict_key already maps to a value
            if inner_dict_key in metadata[item_ark]:
                if text_value != None and text_value not in metadata[item_ark][inner_dict_key]:
                    metadata[item_ark][inner_dict_key] = "{0}|~|{1}".format(
                        metadata[item_ark][inner_dict_key], text_value
                    )
            elif text_value == None:
                pass
            else:
                metadata[item_ark][inner_dict_key] = text_value

            # check if the title field contains the word 'duplicate' or the word 'delete'
            if desc_term_label == "Title" and desc_term_label in metadata[item_ark]:
                if metadata[item_ark][inner_dict_key] == text_value:
                    string_text_value = (str(text_value)).lower()
                    if (bool(re.search(r"\bduplicate", string_text_value)) == True) or (
                        bool(re.search(r"\bdup ", string_text_value)) == True
                    ):
                        metadata[item_ark]["Duplicate"] = "true"
                    if bool(re.search(r"\bdelete\b", string_text_value)) == True:
                        metadata[item_ark]["Delete in Title"] = "true"
            else:
                pass
            if file_location:
                index_of_digi = len("http://digilib.library.ucla.edu/")
                file_location_str = file_location[index_of_digi:]
                if "File Name" not in metadata[item_ark]:
                    metadata[item_ark]["File Name"] = file_location_str
                elif "File Name" in metadata[item_ark]:
                    if file_location_str not in metadata[item_ark]["File Name"]:
                        metadata[item_ark]["File Name"] = "{0}|~|{1}".format(
                            metadata[item_ark]["File Name"], file_location_str
                        )

        # breaks multi-asset works into new childworks
        metadata_copy = metadata.copy()

        for item_ark in metadata_copy.keys():
            ark_prefix = metadata[item_ark]["Item ARK"]
            parent_ark = metadata[item_ark]["Parent ARK"]
            type_object = metadata[item_ark]["Object Type"]
            project_title = metadata[item_ark]["Project Name"]
            if "File Name" in metadata[item_ark]:
                if "|~|" in metadata[item_ark]["File Name"]:
                    file_list = metadata[item_ark]["File Name"].split("|~|")
                    if file_list is not None:
                        file_list.sort()
                        metadata[item_ark]["File Name"] = ""
                        for sequence, file_name in enumerate(file_list, start=1):
                            noid_item_ark = mint(
                                scheme=str(ark_prefix[:11]), naa=str(ark_prefix[11:])
                            )
                            if noid_item_ark not in metadata:
                                metadata[noid_item_ark] = {
                                    "Item ARK": noid_item_ark,
                                    "Object Type": "Page",
                                    "Parent ARK": ark_prefix,
                                    "Title": f"Page {sequence}",
                                    "Project Name": project_title,
                                    "File Name": file_name,
                                    "Item Sequence": str(sequence),
                                }
                            # if childworks are being split, keep original metadata
                            if type_object == "ChildWork":
                                for key, value in metadata[item_ark].items():
                                    if key not in [
                                        "Item ARK",
                                        "Object Type",
                                        "Title",
                                        "File Name",
                                        "Item Sequence",
                                    ]:
                                        metadata[noid_item_ark][key] = value
                        if metadata[item_ark]["Thumbnail"] == "":
                            thumbnail_choice = {
                                "first-thumb": (file_list[0]),
                                "second-thumb": (file_list[-1]),
                                "third-thumb": file_list[random.randint(0, len(file_list) - 1)],
                            }
                            thumbnail_ark = find_ark(metadata, thumbnail_choice[thumbnail])
                            if thumbnail_ark is None:
                                raise DLExportException(
                                    DLExportErrorCode.INVALID_FILENAME,
                                    "Could not find the selected thumbnail file.",
                                )
                            ark_url = "https://iiif.library.ucla.edu/iiif/2/" + str(
                                urllib.parse.quote(thumbnail_ark, safe="")
                            )
                            metadata[item_ark]["Thumbnail"] = ark_url
                        if len(file_list) == 2:
                            name_child_pages(file_list, page_name, metadata, ark_prefix)
        if row_count == 0:
            raise DLExportException(
                DLExportErrorCode.EMPTY_COLLECTION,
                f'Collection "{collection}" has no items.',
            )

        self.csv_headers = csv_headers
        self.metadata = metadata

    def to_json(self) -> str:
        """Return a JSON representation of the loaded metadata."""
        return dumps(self.metadata, sort_keys=True, indent=4)

    def to_csv(self) -> str:
        """Return a CSV representation of the loaded metadata."""
        f = io.StringIO()
        csv_writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)

        csv_writer.writerow([clean(header) for header in self.csv_headers])
        for _, item in sorted(self.metadata.items(), key=lambda entry: entry[0]):
            row = [
                clean(str(item[header])) if header in item and item[header] is not None else ""
                for header in self.csv_headers
            ]
            csv_writer.writerow(row)
        return f.getvalue()

    def get_edited_items(self, db: str, start_date: date, end_date: date) -> None:
        """Load items edited during an inclusive date range.

        Args:
            db: Database name to query.
            start_date: First edit date to include.
            end_date: Last edit date to include.

        Raises:
            DLExportException: If the database is invalid or no items match.
        """
        if db not in self.get_databases():
            raise DLExportException(DLExportErrorCode.INVALID_DATABASE)

        edited_items: list[tuple[Any, ...]] = []
        csv_headers = [
            "Item Created Date",
            "Last Edit Date",
            "Item Ark",
            "Title",
            "Modified By",
            "Created By",
            "Project Title",
        ]
        for item in self._execute_query(
            db,
            EDITED_ITEMS_QUERY,
            {"start_date": start_date, "end_date": end_date},
        ):
            edited_items.append(item)

        if not edited_items:
            raise DLExportException(
                DLExportErrorCode.EMPTY_COLLECTION,
                "No items were edited during the requested date range.",
            )

        self.csv_headers = csv_headers
        self.edited_items = edited_items

    def to_edited_csv(self) -> str:
        """Return a CSV representation of the loaded edited items."""
        f = io.StringIO()
        csv_writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)

        csv_writer.writerow([clean(header) for header in self.csv_headers])
        for item in self.edited_items:
            csv_writer.writerow(item)
        return f.getvalue()

    def to_edited_json(self) -> str:
        """Return a JSON representation of the loaded edited items."""
        rows = [dict(zip(self.csv_headers, item, strict=True)) for item in self.edited_items]
        return dumps(rows, sort_keys=True, indent=4, default=str)


# endregion Main DLExport class and exceptions


####################
# region CLI
####################
class OutputFormat(StrEnum):
    """Supported export formats."""

    CSV = "csv"
    JSON = "json"


app = typer.Typer(
    name="dlexport",
    help="Export metadata from UCLA's Digital Library collections.",
    no_args_is_help=True,
)


def _write_output(content: str, output_path: Path | None) -> None:
    """Write content to a file or standard output, if output_path is None."""
    if output_path is None:
        typer.echo(content, nl=False)
        return
    try:
        output_path.write_text(content, encoding="utf-8")
    except OSError as error:
        raise DLExportException(
            DLExportErrorCode.INVALID_FILENAME,
            f"Could not write output to {output_path}: {error}",
        ) from error


@app.command()
def main(
    database: str = typer.Option(..., "--database", "-d", help="Database to query."),
    collection: str = typer.Option(..., "--collection", "-c", help="Collection to export."),
    # Typer uses OutputFormat enum to display available choices.
    output_format: OutputFormat = typer.Option(
        OutputFormat.CSV,
        "--format",
        "-f",
        help="Desired output format.",
    ),
    output_path: Path | None = typer.Option(
        None,
        "--output-path",
        "-o",
        help="Output file path. Defaults to `output/dlexport_TIMESTAMP.FORMAT`.",
    ),
) -> None:
    """Export a collection's metadata."""
    # Construct default output path if none provided.
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
        output_path = (
            Path("output")  # default to writing to `output/`
            / f"dlexport_{timestamp}.{output_format.value}"
        )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Exporting metadata...", total=None)
            exporter = DLExport()
            exporter.get_metadata(database, collection)
            output = exporter.to_json() if output_format is OutputFormat.JSON else exporter.to_csv()

            if output_path:
                try:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                except OSError as error:
                    raise DLExportException(
                        DLExportErrorCode.INVALID_FILENAME,
                        f"Could not create output directory {output_path.parent}: {error}",
                    ) from error

            _write_output(output, output_path)
        progress.console.print(f"Metadata exported to {output_path}")

    except DLExportException as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=int(error.code)) from error

    except psycopg.Error as error:
        message = DLExportException(DLExportErrorCode.INVALID_QUERY, "The database query failed.")
        typer.echo(str(message), err=True)
        raise typer.Exit(code=int(message.code)) from error


if __name__ == "__main__":
    main()
# endregion CLI
