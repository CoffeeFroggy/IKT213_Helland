"""One SQLite database owns IDs, image bytes, metadata and completed results."""
import csv
import io
import json
import sqlite3
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .image_processing import encode_png, utc_now


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise RuntimeError("Unsupported database schema. Keep a backup and use the matching application version.")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    acquired_at TEXT NOT NULL,
                    captured_at TEXT,
                    completed_at TEXT,
                    source_json TEXT NOT NULL,
                    is_demo INTEGER NOT NULL CHECK (is_demo IN (0,1)),
                    decision TEXT NOT NULL CHECK (decision IN ('PENDING','PASS','REJECT','INCOMPLETE','ERROR')),
                    reason TEXT NOT NULL DEFAULT '',
                    elapsed_ms REAL,
                    config_json TEXT NOT NULL,
                    quality_json TEXT NOT NULL,
                    checks_json TEXT NOT NULL DEFAULT '[]',
                    measurements_json TEXT NOT NULL DEFAULT '{}',
                    detections_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS images (
                    inspection_id INTEGER NOT NULL REFERENCES inspections(id),
                    kind TEXT NOT NULL,
                    png BLOB NOT NULL,
                    PRIMARY KEY (inspection_id, kind)
                );
                CREATE INDEX IF NOT EXISTS inspection_mode_date ON inspections(is_demo, id);
            """)
            # Add operator disposition without rewriting existing images/results.
            con.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in con.execute("PRAGMA table_info(inspections)")}
            additions = [
                ("requires_operator_review", "INTEGER NOT NULL DEFAULT 0 CHECK (requires_operator_review IN (0,1))"),
                ("operator_decision", "TEXT CHECK (operator_decision IN ('PASS','REJECT'))"),
                ("operator_decided_at", "TEXT"),
            ]
            for name, definition in additions:
                if name not in columns:
                    con.execute("ALTER TABLE inspections ADD COLUMN " + name + " " + definition)
            con.execute("PRAGMA user_version=2")

    @contextmanager
    def connection(self):
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def create(self, packet, settings, scenario):
        # Encode before the transaction, so an encoding failure leaves no partial row.
        images = [(k, encode_png(packet[k])) for k in ("original", "gray", "laplace_preview")]
        source = dict(packet["source"])
        if settings.data["demo"]:
            source["placeholder_scenario"] = scenario
        with self.connection() as con:
            cur = con.execute("""INSERT INTO inspections
                (acquired_at,captured_at,source_json,is_demo,decision,config_json,quality_json,requires_operator_review)
                VALUES (?,?,?,?,?,?,?,?)""",
                (packet["acquired_at"], packet["captured_at"], json.dumps(source),
                 int(settings.data["demo"]), "PENDING", json.dumps(settings.data), json.dumps(packet["quality"]),
                 int(packet.get("requires_operator_review", False))))
            inspection_id = cur.lastrowid  # Assigned by SQLite, not by the camera or GUI.
            con.executemany("INSERT INTO images (inspection_id,kind,png) VALUES (?,?,?)",
                            [(inspection_id, kind, sqlite3.Binary(data)) for kind, data in images])
        return inspection_id

    def complete(self, inspection_id, decision, reason, analysis, elapsed_ms):
        annotated = encode_png(analysis["annotated"]) if analysis.get("annotated") is not None else None
        with self.connection() as con:
            cur = con.execute("""UPDATE inspections SET completed_at=?,decision=?,reason=?,elapsed_ms=?,
                checks_json=?,measurements_json=?,detections_json=? WHERE id=? AND decision='PENDING'""",
                (utc_now(), decision, reason, elapsed_ms, json.dumps(analysis["checks"]),
                 json.dumps(analysis["measurements"]), json.dumps(analysis["detections"]), inspection_id))
            if cur.rowcount != 1:
                raise RuntimeError("Inspection is missing or has already been completed: %s" % inspection_id)
            if annotated is not None:
                con.execute("INSERT INTO images (inspection_id,kind,png) VALUES (?,?,?)",
                            (inspection_id, "annotated", sqlite3.Binary(annotated)))

    @staticmethod
    def unpack(row):
        result = dict(row)
        result["is_demo"] = bool(result["is_demo"])
        result["requires_operator_review"] = bool(result["requires_operator_review"])
        for name in ("source", "quality", "config", "checks", "measurements", "detections"):
            result[name] = json.loads(result.pop(name + "_json"))
        return result

    def get(self, inspection_id):
        with self.connection() as con:
            row = con.execute("SELECT * FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if row is None:
            raise ValueError("Inspection does not exist: %s" % inspection_id)
        return self.unpack(row)

    def pending_review(self, is_demo):
        with self.connection() as con:
            row = con.execute("""SELECT * FROM inspections WHERE is_demo=?
                AND requires_operator_review=1 AND operator_decision IS NULL
                AND decision!='PENDING' ORDER BY id DESC LIMIT 1""", (int(is_demo),)).fetchone()
        return self.unpack(row) if row is not None else None

    def save_operator_decision(self, inspection_id, decision, is_demo):
        if decision not in ("PASS", "REJECT"):
            raise ValueError("Choose PASS or REJECT for the operator decision.")
        with self.connection() as con:
            cur = con.execute("""UPDATE inspections SET operator_decision=?,operator_decided_at=?
                WHERE id=? AND is_demo=? AND requires_operator_review=1
                AND decision!='PENDING' AND operator_decision IS NULL""",
                (decision, utc_now(), inspection_id, int(is_demo)))
            if cur.rowcount != 1:
                raise ValueError("Inspection is not awaiting an operator decision, or a choice was already saved.")

    def history(self, is_demo, limit=500):
        # Avoid loading image BLOBs into the history view.
        with self.connection() as con:
            rows = con.execute("SELECT * FROM inspections WHERE is_demo=? ORDER BY id DESC LIMIT ?",
                               (int(is_demo), limit)).fetchall()
        return [self.unpack(row) for row in rows]

    def image(self, inspection_id, kind="annotated"):
        with self.connection() as con:
            row = con.execute("SELECT png FROM images WHERE inspection_id=? AND kind=?",
                              (inspection_id, kind)).fetchone()
            if row is None and kind == "annotated":
                row = con.execute("SELECT png FROM images WHERE inspection_id=? AND kind='original'",
                                  (inspection_id,)).fetchone()
        if row is None:
            raise ValueError("Stored image is missing.")
        return bytes(row[0])

    def statistics(self, is_demo):
        with self.connection() as con:
            rows = con.execute("SELECT decision,checks_json,detections_json,requires_operator_review,operator_decision FROM inspections WHERE is_demo=?",
                               (int(is_demo),)).fetchall()
        counts = {name: 0 for name in ("PENDING", "PASS", "REJECT", "INCOMPLETE", "ERROR")}
        categories = {"scratch": 0, "crack": 0, "presence": 0, "shape": 0, "dimensions": 0}
        operator_counts = {"PASS": 0, "REJECT": 0, "AWAITING": 0}
        for row in rows:
            counts[row["decision"]] += 1
            if row["requires_operator_review"] and row["decision"] != "PENDING":
                operator_counts[row["operator_decision"] or "AWAITING"] += 1
            for label in {d["label"] for d in json.loads(row["detections_json"])}:
                if label in categories:
                    categories[label] += 1
            for c in json.loads(row["checks_json"]):
                if c["state"] == "FAIL" and c["name"] in categories:
                    categories[c["name"]] += 1
        assessed = counts["PASS"] + counts["REJECT"]
        decided = operator_counts["PASS"] + operator_counts["REJECT"]
        return {"counts": counts, "categories": categories, "total": len(rows),
                "pass_rate": counts["PASS"] / assessed if assessed else None,
                "operator_counts": operator_counts,
                "operator_pass_rate": operator_counts["PASS"] / decided if decided else None}

    def export(self, path, is_demo, rejects_only=False):
        """Export a consistent snapshot; CSV metadata and, in ZIP, rejected originals."""
        target = Path(path)
        if target.suffix.lower() not in (".csv", ".zip"):
            raise ValueError("Choose a .csv or .zip output file.")
        with self.connection() as con:
            con.execute("BEGIN")  # One read snapshot for rows and images.
            sql = "SELECT * FROM inspections WHERE is_demo=?"
            if rejects_only:
                sql += " AND ((requires_operator_review=1 AND operator_decision='REJECT') OR (requires_operator_review=0 AND decision='REJECT'))"
            rows = con.execute(sql + " ORDER BY id", (int(is_demo),)).fetchall()
            records = [self.unpack(row) for row in rows]
            text = io.StringIO(newline="")
            fields = ["id", "is_demo", "acquired_at", "captured_at", "automatic_result", "reason",
                      "requires_operator_review", "operator_decision", "operator_decided_at",
                      "width_mm", "height_mm", "defects", "elapsed_ms"]
            writer = csv.DictWriter(text, fields)
            writer.writeheader()
            for r in records:
                flat = {k: r.get(k) for k in fields}
                flat.update({"automatic_result": r["decision"],
                             "width_mm": r["measurements"].get("width_mm"),
                             "height_mm": r["measurements"].get("height_mm"),
                             "defects": ", ".join(sorted({d["label"] for d in r["detections"]}))})
                writer.writerow(flat)
            if target.suffix.lower() == ".csv":
                target.write_text(text.getvalue(), encoding="utf-8-sig")
            else:
                with zipfile.ZipFile(str(target), "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("results.csv", text.getvalue().encode("utf-8-sig"))
                    archive.writestr("records.json", json.dumps(records, indent=2))
                    for r in records:
                        final = r["operator_decision"] if r["requires_operator_review"] else r["decision"]
                        if final != "REJECT":
                            continue
                        for image_row in con.execute("SELECT kind,png FROM images WHERE inspection_id=? AND kind IN ('original','annotated')", (r["id"],)):
                            archive.writestr("rejected/%06d_%s.png" % (r["id"], image_row["kind"]), bytes(image_row["png"]))
        return len(records)
