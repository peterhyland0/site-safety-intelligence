"""A build missing raw data never goes live: the extracted OSHA files are swapped in whole or not at all, and a build
whose daily tables shrank against the live one fails its checks (ssi/pipeline/download.py, build.py)."""
import json
import zipfile
from datetime import date

import pytest

from ssi.pipeline import build, download


def prev(inspections=1000, violations=3000, since=date(2016, 9, 23)):
    sums = {"osha.inspection": f"{inspections}:123", "osha.violation": f"{violations}:456", "osha.accident": "50:9"}
    return {"history_since": since, "table_checksums": json.dumps(sums)}


def test_a_build_short_of_the_live_one_fails():
    # one of the ~268 violation files missing: every other check passes against the files that are there
    c = build.shrink_check(prev(), {"osha.inspection": 1003, "osha.violation": 2700}, "2016-09-24")
    assert c["severity"] == "error" and not c["pass"] and c["actual"] == {"osha.violation": 0.9}


def test_a_day_of_new_data_passes():
    c = build.shrink_check(prev(), {"osha.inspection": 995, "osha.violation": 2990}, "2016-09-26")
    assert c["pass"] and c["actual"] == {"osha.inspection": 0.995, "osha.violation": 0.9967}


def test_a_changed_history_setting_or_no_live_build_isnt_compared(monkeypatch):
    assert build.shrink_check(None, {"osha.inspection": 1}, "2016-09-24") is None
    assert build.shrink_check(prev(), {"osha.inspection": 1}, "2021-09-24") is None  # SSI_HISTORY_YEARS 10 -> 5
    assert build.shrink_check(prev(), {"osha.inspection": 1}, None) is None  # -> 0 (all years)
    monkeypatch.setenv("SSI_ALLOW_SHRINK", "1")
    assert build.shrink_check(prev(), {"osha.inspection": 1}, "2016-09-24") is None


def _zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)


def test_extracted_files_are_swapped_in_whole(tmp_path):
    out = tmp_path / "violation"
    out.mkdir()
    (out / "old.csv").write_text("last week's")
    z = tmp_path / "OSHA_violation.zip"
    _zip(z, {"violation_0.csv": "a,b\n1,2\n", "violation_1.csv": "a,b\n3,4\n"})
    download.extract(z, out)
    assert sorted(p.name for p in out.iterdir()) == ["violation_0.csv", "violation_1.csv"]
    assert not (tmp_path / "violation.part").exists()


def test_a_failed_extraction_leaves_the_last_whole_set(tmp_path, monkeypatch):
    out = tmp_path / "violation"
    out.mkdir()
    (out / "violation_0.csv").write_text("last week's")
    z = tmp_path / "OSHA_violation.zip"
    _zip(z, {"violation_0.csv": "new", "violation_1.csv": "new"})

    def disk_full(self, path=None, members=None, pwd=None):
        (path / "violation_0.csv").parent.mkdir(parents=True, exist_ok=True)
        (path / "violation_0.csv").write_text("ne")  # cut short
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", disk_full)
    with pytest.raises(OSError):
        download.extract(z, out)
    assert [p.name for p in out.iterdir()] == ["violation_0.csv"] and (out / "violation_0.csv").read_text() == "last week's"
