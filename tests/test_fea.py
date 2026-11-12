"""Offline regression tests: borrowed-session safety, script transport, checks and
post-processing helpers. None of these connect to ANSYS."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fea
import fea_checks
import fea_post

DECK = """/batch
/units,MKS
et,1,186
nblock,3,,3
(1i9,3e20.9e3)
        1     1.000000000E-01    -2.000000000E-02     0.000000000E+00
        2    -1.000000000E-01     0.000000000E+00     3.000000000E-02
        3     0.000000000E+00     1.000000000E-01    -1.000000000E-01
-1
et,2,174      ! contact
eblock,19,solid,,2
(19i9)
-1
keyop,2,12,5
/solu
airl,6
solve
"""


class RunnerTests(unittest.TestCase):
    def test_script_exceptions_fail_instead_of_becoming_success(self):
        scope = {}
        exec(fea.envelope("raise ValueError('bad load')", "workbench"), scope)
        with self.assertRaisesRegex(RuntimeError, "bad load"):
            fea.decode_result(scope["wb_script_result"])

    def test_paths_and_unicode_survive_script_transport(self):
        scope = {}
        value = "C:\\a folder\\frame's \u03b1.step"
        exec(fea.envelope("wb_script_result = " + repr(value), "workbench"), scope)
        self.assertEqual(fea.decode_result(scope["wb_script_result"]), value)

    def test_arguments_reach_server_scripts(self):
        scope = {}
        source = fea.prelude("workbench", {"name": "Bracket \u03b1 'case'"}) + "wb_script_result = [fea_args['name'], study_root]"
        exec(fea.envelope(source, "workbench"), scope)
        name, root = fea.decode_result(scope["wb_script_result"])
        self.assertEqual(name, "Bracket \u03b1 'case'")
        self.assertEqual(Path(root), fea.STUDY)

    def test_mechanical_helpers_compile(self):
        compile(fea.server_script(fea.SCRIPTS / "report_mechanical.py", "mechanical", {"views": ["Iso"]}), "x", "exec")
        for script in list(fea.SCRIPTS.glob("*.py")) + list((fea.ROOT / "examples" / "stages").glob("*.py")):
            compile(script.read_text(encoding="utf-8"), str(script), "exec")

    def test_missing_response_fails(self):
        with self.assertRaises(RuntimeError):
            fea.decode_result(None)

    def test_validation_rejects_empty_project(self):
        self.assertFalse(fea.validate("workbench", {"systems": []})["ok"])
        self.assertFalse(fea.validate("mechanical", {"analyses": []})["ok"])

    def test_remote_hosts_are_refused(self):
        with patch.object(fea, "LOCAL_CONFIG", Path(tempfile.gettempdir()) / "missing-fea.local.json"):
            with self.assertRaisesRegex(ValueError, "port"):
                fea.configuration("workbench")
            with patch("json.loads", return_value={"workbench": {"host": "10.0.0.5", "port": 5, "security": "wnua"}}):
                with self.assertRaisesRegex(ValueError, "local"):
                    fea.configuration("workbench")

    def test_remember_port_keeps_other_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder) / "fea.local.json"
            local.write_text(json.dumps({"workbench": {"port": 1}}))
            with patch.object(fea, "LOCAL_CONFIG", local):
                fea.remember_port("mechanical", 2)
            self.assertEqual(json.loads(local.read_text()), {"workbench": {"port": 1}, "mechanical": {"port": 2}})

    def test_mechanical_attach_does_not_clear_or_exit(self):
        endpoint = {"host": "127.0.0.1", "port": 10000, "security": "wnua"}
        with patch("socket.create_connection"), patch("ansys.mechanical.core.connect_to_mechanical") as connect:
            with fea.Session("mechanical", endpoint, 2):
                pass
            self.assertFalse(connect.call_args.kwargs["clear_on_connect"])
            self.assertFalse(connect.call_args.kwargs["cleanup_on_exit"])
            connect.return_value.exit.assert_not_called()

    def test_help_lists_every_command_with_its_kind(self):
        text = fea.build_parser().format_help()
        for command in ("inspect", "validate", "mesh", "solve", "report", "stage", "run", "save"):
            self.assertIn(command, text)
        self.assertIn("[saves]", text)


class ExpectationTests(unittest.TestCase):
    snapshot = {
        "analyses": [{"name": "Static", "solution_state": "NotSolved"}],
        "project": {"name": "Project", "children": [
            {"name": "Plate", "DataModelObjectCategory": "Body", "Material": "Steel", "children": []},
            {"name": "Rib", "DataModelObjectCategory": "Body", "Material": "Aluminum", "children": []},
            {"name": "Old", "DataModelObjectCategory": "Body", "Suppressed": "True", "children": []},
            {"name": "Fixed", "DataModelObjectCategory": "FixedSupport", "children": []}]}}

    def issues(self, expected):
        return list(fea_checks.expectation_issues("mechanical", self.snapshot, expected))

    def test_empty_expectations_pass(self):
        self.assertEqual(self.issues({}), [])

    def test_counts_ignore_suppressed_objects(self):
        self.assertEqual(self.issues({"counts": {"Body": 2}}), [])
        self.assertEqual(len(self.issues({"counts": {"Body": 3}})), 1)

    def test_forbidden_materials_and_solved(self):
        found = self.issues({"forbid_categories": ["FixedSupport"], "materials": {"Plate": "Steel", "*": "Steel"},
                             "require_solved": True, "analysis": "Static"})
        self.assertEqual(len(found), 3, found)

    def test_missing_analysis(self):
        self.assertIn("no analysis", self.issues({"analysis": "Modal"})[0])


class PostTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.deck = Path(self.folder.name) / "input.dat"
        self.deck.write_text(DECK)

    def tearDown(self):
        self.folder.cleanup()

    def test_nodes_and_summary(self):
        nodes = fea_post.read_nodes(self.deck)
        self.assertEqual(nodes[2], (-0.1, 0.0, 0.03))
        summary = fea_post.deck_summary(self.deck)
        self.assertEqual((summary["nodes"], summary["elements"], summary["units"]), (3, 2, "MKS"))
        self.assertEqual(summary["element_types"], {"186": 1, "174": 1})
        self.assertEqual(summary["review_commands"]["keyopt"], 1)
        self.assertTrue(summary["inertia_relief"])
        self.assertEqual(summary["displacement_constraints"], 0)

    def test_deck_rules(self):
        self.assertEqual(fea_post.check_deck(self.deck, {"require": [r"^\s*airl\s*,\s*6"], "units": "MKS"}), [])
        issues = fea_post.check_deck(self.deck, {"forbid": [r"^\s*airl"], "units": "BIN"})
        self.assertEqual(len(issues), 2)

    def test_result_table(self):
        table = Path(self.folder.name) / "r.txt"
        table.write_text("Node Number\tDirectional Deformation (mm)\n1\t3.9e-004\n2\t-1.5e-003\n", encoding="utf-8-sig")
        self.assertEqual(fea_post.read_result_table(table), {1: 3.9e-4, 2: -1.5e-3})
        self.assertEqual(fea_post.table_unit(table), "mm")

    def test_rigid_fit_removes_rigid_motion_exactly(self):
        coords = {1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0), 4: (0, 0, 1), 5: (1, 1, 1)}
        motion = [0.1, -0.2, 0.05, 0.01, -0.02, 0.03]
        tx, ty, tz, rx, ry, rz = motion
        disp = [{}, {}, {}]
        for n, (x, y, z) in coords.items():
            rigid = (tx + ry * z - rz * y, ty + rz * x - rx * z, tz + rx * y - ry * x)
            for k in range(3):
                disp[k][n] = rigid[k] + (0.5 if n == 5 and k == 1 else 0)
        fit = fea_post.fit_rigid_motion(coords, disp, [1, 2, 3, 4])
        for a, b in zip(fit, motion):
            self.assertAlmostEqual(a, b)
        relative = fea_post.relative_displacement(5, coords, disp, fit)
        self.assertTrue(math.isclose(relative[1], 0.5) and abs(relative[0]) < 1e-12)

    def test_rigid_fit_rejects_collinear_nodes(self):
        coords = {1: (0, 0, 0), 2: (1, 0, 0), 3: (2, 0, 0)}
        disp = [{n: 0.0 for n in coords} for _ in range(3)]
        with self.assertRaises(ValueError):
            fea_post.fit_rigid_motion(coords, disp, coords)


if __name__ == "__main__":
    unittest.main()
