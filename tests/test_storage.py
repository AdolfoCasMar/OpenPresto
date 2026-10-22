import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpresto.budget import Budget, BudgetConcept, BudgetMeasurement, BudgetRelation
from openpresto.storage import (
    StorageError, dumps, loads, to_dict, from_dict, save_budget, load_budget,
)


class StorageTests(unittest.TestCase):
    def test_v4_precision_and_text_roundtrip_without_changing_measurements(self):
        before = to_dict(self.budget)
        self.budget.root_quantity_decimals = 0
        document = to_dict(self.budget)
        self.assertEqual(document['version'], 4)
        restored = loads(dumps(self.budget))
        self.assertEqual(restored.root_quantity_decimals, 0)
        self.assertEqual(to_dict(restored), document)
        self.assertEqual(document['measurements'], before['measurements'])
        document['calculation']['root_quantity_decimals'] = True
        with self.assertRaises(StorageError):
            from_dict(document)

    def setUp(self):
        self.budget = Budget("OBRA")
        self.budget.add_concept(BudgetConcept("OBRA", summary="Reforma áé ñ"))
        self.budget.add_concept(BudgetConcept(
            "P", unit="m²", summary="Pavimento", nature="partida",
            base_price="12.3456700"))
        self.budget.add_relation(BudgetRelation(
            "OBRA", "P", quantity="99.9900", position=1, id="r1"))
        self.budget.add_measurement(BudgetMeasurement(
            "r1", comment="A deducir", n_lines="-1.0", length="2.500",
            width=None, height="0", id="m1"))

    def test_roundtrip_preserves_exact_decimal_and_unicode(self):
        loaded = loads(dumps(self.budget))
        self.assertEqual(to_dict(loaded), to_dict(self.budget))
        self.assertEqual(loaded.concepts["P"].base_price.as_tuple(),
                         Decimal("12.3456700").as_tuple())
        self.assertIsNone(loaded.measurements[0].width)
        self.assertEqual(loaded.measurements[0].height, Decimal("0"))
        self.assertEqual(loaded.concepts["OBRA"].summary, "Reforma áé ñ")

    def test_save_and_load_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presupuesto.openpresto.json"
            save_budget(self.budget, path)
            self.assertEqual(to_dict(load_budget(path)), to_dict(self.budget))
            self.assertFalse(any(p.suffix == ".tmp" for p in Path(directory).iterdir()))

    def test_atomic_failure_does_not_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.json"
            path.write_text("CONTENIDO ANTERIOR", encoding="utf-8")
            invalid = Budget("NO_EXISTE")
            with self.assertRaises(StorageError):
                save_budget(invalid, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "CONTENIDO ANTERIOR")

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StorageError):
                load_budget(Path(directory) / "ausente.json")

    def test_bad_format_or_version_rejected(self):
        for key, value in (("version", 2), ("version", True), ("format", "BC3")):
            with self.subTest(key=key, value=value):
                doc = to_dict(self.budget)
                doc[key] = value
                with self.assertRaises(StorageError):
                    from_dict(doc)

    def test_invalid_links_or_cycles_rejected(self):
        doc = to_dict(self.budget)
        doc["relations"][0]["child_code"] = "NO_EXISTE"
        with self.assertRaises(StorageError):
            from_dict(doc)
        doc = to_dict(self.budget)
        doc["relations"].append({"id": "r2", "parent_code": "P",
                                 "child_code": "OBRA", "quantity": "1",
                                 "position": 1})
        with self.assertRaises(StorageError):
            from_dict(doc)

    def test_duplicate_concept_relation_or_measurement_rejected(self):
        for key in ("concepts", "relations", "measurements"):
            with self.subTest(key=key):
                doc = to_dict(self.budget)
                doc[key].append(dict(doc[key][0]))
                with self.assertRaises(StorageError):
                    from_dict(doc)

    def test_invalid_decimal_rejected(self):
        for value in (1.25, "NaN", "Infinity", "abc"):
            with self.subTest(value=value):
                doc = to_dict(self.budget)
                doc["concepts"][1]["base_price"] = value
                with self.assertRaises(StorageError):
                    from_dict(doc)

    def test_invalid_json_and_duplicate_keys_rejected(self):
        for source in ('{', '{"x":1,"x":2}', 'NaN'):
            with self.subTest(source=source), self.assertRaises(StorageError):
                loads(source)

    def test_invalid_root_rejected(self):
        doc = to_dict(self.budget)
        doc["root_code"] = "PERDIDO"
        with self.assertRaises(StorageError):
            from_dict(doc)

    def test_empty_budget_roundtrip(self):
        empty = Budget()
        self.assertEqual(to_dict(loads(dumps(empty))), to_dict(empty))

    def test_preserve_relations_and_measurements_order(self):
        self.budget.add_concept(BudgetConcept("R", base_price="1"))
        self.budget.add_relation(BudgetRelation("OBRA", "R", id="r2", position=2))
        self.budget.add_measurement(BudgetMeasurement("r1", n_lines="2", id="m2"))
        restored = loads(dumps(self.budget))
        self.assertEqual([r.id for r in restored.relations], ["r1", "r2"])
        self.assertEqual([m.id for m in restored.measurements], ["m1", "m2"])


if __name__ == "__main__":
    unittest.main()
