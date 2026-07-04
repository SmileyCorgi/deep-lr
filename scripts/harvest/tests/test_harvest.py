#!/usr/bin/env python3
"""
Unit tests for the harvest pipeline's pure logic and I/O contract.
Run from the repo root:  python -m unittest discover scripts/harvest/tests -v
Stdlib-only (unittest), matching the repo's no-dependency doctrine.
"""
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import manifestio
import dedup


def row(**kw) -> dict:
    r = {h: "" for h in manifestio.HEADERS}
    r.update(kw)
    return r


class TestNormalization(unittest.TestCase):
    def test_norm_title(self):
        self.assertEqual(dedup.norm_title("Towards  Better QA: A Survey!"),
                         "towards better qa a survey")

    def test_norm_arxiv_strips_version(self):
        self.assertEqual(dedup.norm_arxiv("2506.01234v3"), "2506.01234")
        self.assertEqual(dedup.norm_arxiv("2506.01234"), "2506.01234")

    def test_norm_doi(self):
        self.assertEqual(dedup.norm_doi("https://doi.org/10.18653/v1/2026.acl-long.1"),
                         "10.18653/v1/2026.acl-long.1")
        self.assertEqual(dedup.norm_doi("DOI:10.1234/X"), "10.1234/x")


class TestAuthorOverlap(unittest.TestCase):
    def test_first_author_match(self):
        self.assertTrue(dedup.author_overlap_ok(
            "Smith, Jane; Doe, John", "Smith, Jane; Lee, Kim"))

    def test_half_overlap(self):
        self.assertTrue(dedup.author_overlap_ok(
            "Doe, John; Lee, Kim", "Lee, Kim; Doe, John; Wu, Ann"))

    def test_no_overlap(self):
        self.assertFalse(dedup.author_overlap_ok(
            "Smith, Jane", "Doe, John"))

    def test_empty_authors_never_match(self):
        self.assertFalse(dedup.author_overlap_ok("", "Smith, Jane"))


class TestClustering(unittest.TestCase):
    def test_same_arxiv_id_merges_despite_different_title(self):
        rows = [row(title="Old Preprint Title", authors="Smith, Jane",
                    arxiv_id="2506.01234v1", venue="arXiv", year="2025"),
                row(title="Completely New Camera Ready Name", authors="Smith, Jane",
                    arxiv_id="2506.01234v3", venue="ACL", year="2026")]
        clusters = dedup.cluster_indices(rows)
        self.assertEqual(len(clusters), 1)

    def test_retitled_preprint_fuzzy_match(self):
        rows = [row(title="Towards Robust Retrieval Augmented Generation for Long Documents",
                    authors="Smith, Jane; Doe, John", venue="arXiv", year="2025"),
                row(title="Robust Retrieval Augmented Generation for Long Documents",
                    authors="Smith, Jane; Doe, John", venue="ACL", year="2026")]
        clusters = dedup.cluster_indices(rows)
        self.assertEqual(len(clusters), 1)

    def test_same_title_different_authors_stays_separate(self):
        rows = [row(title="Attention Is All You Need", authors="Smith, Jane"),
                row(title="Attention Is All You Need", authors="Doe, John")]
        clusters = dedup.cluster_indices(rows)
        self.assertEqual(len(clusters), 2)


class TestCanonicalSelection(unittest.TestCase):
    def rank_key(self, r):
        return (dedup.source_rank(r), -int(r["year"] or 0), r["venue"],
                dedup.TRACK_PRIORITY.get(r["track"], 99))

    def test_archival_beats_earlier_preprint(self):
        preprint = row(title="X", venue="WS", year="2025", arxiv_id="2506.1",
                       track="accepted")
        camera = row(title="X", venue="ACL", year="2026",
                     anthology_id="2026.acl-long.1", track="main")
        winner, others = dedup.pick_canonical([preprint, camera], self.rank_key)
        self.assertEqual(winner["venue"], "ACL")
        # Winner backfills the arxiv_id it lacked from the loser.
        self.assertEqual(winner["arxiv_id"], "2506.1")
        self.assertIn("also accepted at: WS 2025", winner["notes"])

    def test_latest_year_wins_within_same_source_rank(self):
        a = row(title="X", venue="WS", year="2025", openreview_id="abc")
        b = row(title="X", venue="ICLR", year="2026", openreview_id="abc")
        winner, _ = dedup.pick_canonical([a, b], self.rank_key)
        self.assertEqual(winner["year"], "2026")


class TestCarryOver(unittest.TestCase):
    def test_rerun_preserves_download_state_and_ids(self):
        old = [row(id="ACL_2026_001", venue="ACL", year="2026", slug="smith-qa",
                   downloaded="yes", notes="hand note"),
               row(id="ACL_2026_002", venue="ACL", year="2026", slug="doe-ir",
                   downloaded="yes")]
        new = [row(venue="ACL", year="2026", slug="smith-qa", title="QA"),
               row(venue="ACL", year="2026", slug="doe-ir", title="IR"),
               row(venue="ACL", year="2026", slug="wu-new", title="New")]
        stats = dedup.carry_over_and_assign_ids(new, old)
        self.assertEqual(stats["carried"], 2)
        self.assertEqual(new[0]["id"], "ACL_2026_001")
        self.assertEqual(new[0]["downloaded"], "yes")
        self.assertEqual(new[0]["notes"], "hand note")
        # New row numbered AFTER the existing max — existing ids never move.
        self.assertEqual(new[2]["id"], "ACL_2026_003")
        self.assertEqual(new[2]["downloaded"], "")

    def test_fresh_run_assigns_sequential_ids(self):
        new = [row(venue="ACL", year="2026", slug="a", title="A"),
               row(venue="ACL", year="2026", slug="b", title="B")]
        dedup.carry_over_and_assign_ids(new, [])
        self.assertEqual([r["id"] for r in new], ["ACL_2026_001", "ACL_2026_002"])

    def test_venue_change_is_treated_as_new_row(self):
        old = [row(id="WS_2025_001", venue="WS", year="2025", slug="smith-qa",
                   downloaded="yes")]
        new = [row(venue="ACL", year="2026", slug="smith-qa", title="QA")]
        stats = dedup.carry_over_and_assign_ids(new, old)
        self.assertEqual(stats["carried"], 0)
        self.assertEqual(len(stats["dropped"]), 1)
        self.assertEqual(new[0]["downloaded"], "")  # must re-download


class TestManifestIO(unittest.TestCase):
    def test_roundtrip_with_hostile_characters(self):
        rows = [row(id="A_1_001", title="Łukasz's re\\view:\tan essay",
                    authors="Łukasz, K.", venue="A", year="1", slug="x")]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.tsv"
            manifestio.write_rows(p, rows)
            back = manifestio.read_rows(p)
        self.assertEqual(back[0]["title"], rows[0]["title"])
        self.assertEqual(back[0]["authors"], "Łukasz, K.")

    def test_v1_manifest_upgrades_on_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.tsv"
            with p.open("w", encoding="utf-8", newline="") as f:
                f.write("\t".join(manifestio.V1_HEADERS) + "\n")
                vals = {h: "" for h in manifestio.V1_HEADERS}
                vals.update(id="ACL_2026_001", title="T", downloaded="yes")
                f.write("\t".join(vals[h] for h in manifestio.V1_HEADERS) + "\n")
            back = manifestio.read_rows(p)
        self.assertEqual(back[0]["downloaded"], "yes")
        self.assertEqual(back[0]["doi"], "")        # upgraded field present
        self.assertEqual(back[0]["code_url"], "")

    def test_header_mismatch_exits_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.tsv"
            p.write_text("foo\tbar\n1\t2\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                manifestio.read_rows(p)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.tsv"
            body = "\t".join(manifestio.HEADERS) + "\n\n" + \
                   "\t".join(["A_1_001"] + [""] * (len(manifestio.HEADERS) - 1)) + "\n\n"
            p.write_text(body, encoding="utf-8")
            back = manifestio.read_rows(p)
        self.assertEqual(len(back), 1)

    def test_pdf_ok_rejects_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.pdf"
            good.write_bytes(b"%PDF-1.5" + b"x" * 2000 + b"%%EOF\n")
            bad = Path(d) / "bad.pdf"
            bad.write_bytes(b"%PDF-1.5" + b"x" * 2000)  # no trailer
            small = Path(d) / "small.pdf"
            small.write_bytes(b"%PDF-1.5%%EOF")
            self.assertTrue(manifestio.pdf_ok(good))
            self.assertFalse(manifestio.pdf_ok(bad))
            self.assertFalse(manifestio.pdf_ok(small))


if __name__ == "__main__":
    unittest.main()
