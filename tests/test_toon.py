"""Tests for the TOON encoder."""

from aperture.compression.toon import is_tabular_records, to_toon
from aperture.tokenization import count_tokens


class TestIsTabular:
    def test_uniform_records(self):
        rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        assert is_tabular_records(rows)

    def test_single_row_not_tabular(self):
        assert not is_tabular_records([{"id": 1}])

    def test_mixed_keys_not_tabular(self):
        rows = [{"id": 1, "name": "a"}, {"id": 2, "title": "b"}]
        assert not is_tabular_records(rows)

    def test_non_list_not_tabular(self):
        assert not is_tabular_records({"id": 1})

    def test_empty_list_not_tabular(self):
        assert not is_tabular_records([])


class TestToon:
    def test_table_encoding_round_trip(self):
        rows = [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob", "role": "user"},
            {"id": 3, "name": "Carol", "role": "admin"},
        ]
        out = to_toon(rows, name="users")
        assert "users[3]{id,name,role}:" in out
        assert "1,Alice,admin" in out
        assert "2,Bob,user" in out
        assert "# end users" in out

    def test_table_smaller_than_json(self):
        rows = [
            {"id": i, "name": f"user{i}", "email": f"u{i}@example.com", "role": "member"}
            for i in range(20)
        ]
        toon_tokens = count_tokens(to_toon(rows, name="users")).tokens
        json_tokens = count_tokens(rows).tokens
        assert toon_tokens < json_tokens

    def test_aperture_summary_passthrough(self):
        payload = {
            "_aperture_summary": {"total_rows": 100, "sampled_rows": 5},
            "sample": [
                {"id": 1, "title": "x"},
                {"id": 2, "title": "y"},
                {"id": 3, "title": "z"},
            ],
        }
        out = to_toon(payload, name="issues")
        assert "TOON" in out
        assert "issues_sample[3]{id,title}:" in out

    def test_quotes_strings_with_commas(self):
        rows = [{"text": "hello, world"}, {"text": "no comma"}]
        out = to_toon(rows)
        assert '"hello, world"' in out

    def test_non_tabular_falls_back_to_json(self):
        out = to_toon({"single": "object"})
        assert out.startswith("{")
