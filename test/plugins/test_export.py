"""Test the beets.export utilities associated with the export plugin."""

import json
import re  # used to test csv format
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from beets.test.helper import IOMixin, PluginTestCase

MUSICBRAINZ_FIELDS = {
    "mb_albumartistid",
    "mb_albumartistids",
    "mb_albumid",
    "mb_artistid",
    "mb_artistids",
    "mb_releasegroupid",
    "mb_releasetrackid",
    "mb_trackid",
    "mb_workid",
}


class ExportPluginTest(IOMixin, PluginTestCase):
    plugin = "export"

    def setUp(self):
        super().setUp()
        self.test_values = {"title": "xtitle", "album": "xalbum"}

    def execute_command(self, format_type, artist):
        query = ",".join(self.test_values.keys())
        return self.run_with_output(
            "export", "-f", format_type, "-i", query, artist
        )

    def create_item(self):
        (item,) = self.add_item_fixtures()
        item.artist = "xartist"
        item.title = self.test_values["title"]
        item.album = self.test_values["album"]
        item.write()
        item.store()
        return item

    def create_item_with_musicbrainz_fields(self):
        item = self.create_item()
        item.mb_albumid = "album-id"
        item.mb_trackid = "track-id"
        item.write()
        item.store()
        return item

    def test_json_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="json", artist=item1.artist)
        json_data = json.loads(out)[0]
        for key, val in self.test_values.items():
            assert key in json_data
            assert val == json_data[key]

    def test_include_keys_glob_matches_tag_fields(self):
        item = self.create_item_with_musicbrainz_fields()
        out = self.run_with_output("export", "-i", "mb*", item.artist)
        json_data = json.loads(out)[0]
        assert set(json_data) == MUSICBRAINZ_FIELDS
        assert json_data["mb_albumid"] == "album-id"
        assert json_data["mb_trackid"] == "track-id"
        assert "mb*" not in json_data

    def test_include_keys_glob_with_comma_separated_keys(self):
        item = self.create_item_with_musicbrainz_fields()
        out = self.run_with_output("export", "-i", "title,mb*", item.artist)
        json_data = json.loads(out)[0]
        assert set(json_data) == MUSICBRAINZ_FIELDS | {"title"}
        assert json_data["title"] == self.test_values["title"]
        assert json_data["mb_albumid"] == "album-id"
        assert json_data["mb_trackid"] == "track-id"

    def test_include_keys_glob_with_repeated_overlapping_selectors(self):
        item = self.create_item_with_musicbrainz_fields()
        out = self.run_with_output(
            "export", "-i", "mb*", "-i", "mb_album*", item.artist
        )
        pairs = json.loads(out, object_pairs_hook=list)[0]
        json_data = dict(pairs)
        assert set(json_data) == MUSICBRAINZ_FIELDS
        assert len(pairs) == len(json_data)
        assert json_data["mb_albumid"] == "album-id"
        assert json_data["mb_trackid"] == "track-id"
        assert "mb*" not in json_data

    def test_include_keys_glob_matches_library_fields(self):
        item = self.create_item_with_musicbrainz_fields()
        out = self.run_with_output(
            "export", "--library", "-i", "title", "-i", "mb*", item.artist
        )
        json_data = json.loads(out)[0]
        assert set(json_data) == MUSICBRAINZ_FIELDS | {"title"}
        assert json_data["title"] == self.test_values["title"]
        assert json_data["mb_albumid"] == "album-id"
        assert json_data["mb_trackid"] == "track-id"

    def test_include_keys_glob_with_no_matches(self):
        item = self.create_item()
        out = self.run_with_output(
            "export", "--library", "-i", "unknown*", item.artist
        )
        assert json.loads(out) == [{}]

    def test_include_keys_glob_with_no_tag_matches(self):
        item = self.create_item()
        out = self.run_with_output("export", "-i", "unknown*", item.artist)
        assert json.loads(out) == [{}]

    def test_jsonlines_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="jsonlines", artist=item1.artist)
        json_data = json.loads(out)
        for key, val in self.test_values.items():
            assert key in json_data
            assert val == json_data[key]

    def test_csv_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="csv", artist=item1.artist)
        csv_list = re.split("\r", re.sub("\n", "", out))
        head = re.split(",", csv_list[0])
        vals = re.split(",|\r", csv_list[1])
        for index, column in enumerate(head):
            assert self.test_values.get(column, None) is not None
            assert vals[index] == self.test_values[column]

    def test_xml_output(self):
        item1 = self.create_item()
        out = self.execute_command(format_type="xml", artist=item1.artist)
        library = ElementTree.fromstring(out)
        assert isinstance(library, Element)
        for track in library[0]:
            for details in track:
                tag = details.tag
                txt = details.text
                assert tag in self.test_values, tag
                assert self.test_values[tag] == txt, txt
