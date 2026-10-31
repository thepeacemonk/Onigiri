import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


class KomeDeckProgressTests(unittest.TestCase):
    def test_parent_counts_include_descendants_once(self):
        source = (Path(__file__).resolve().parents[1] / "things_theme/__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_full_deck_tree_payload")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))

        def node(did, name, children=()):
            return SimpleNamespace(deck_id=did, name=name, children=children)

        root = node(0, "", [node(1, "Parent", [node(2, "Child", [node(3, "Grandchild")]), node(4, "Sibling")])])
        decks = SimpleNamespace(get_current_id=lambda: 1, name=lambda did: str(did), get=lambda did: {})
        mw = SimpleNamespace(col=SimpleNamespace(sched=SimpleNamespace(deck_due_tree=lambda: root), decks=decks))
        namespace = {
            "mw": mw,
            "_studied_today_by_deck": lambda: {1: 1, 2: 2, 3: 3, 4: 4},
            "_custom_deck_icons": lambda: {},
            "_is_internal_ready_deck": lambda name: False,
            "_resolved_deck_icon": lambda did, icons: None,
        }
        exec(compile(module, "things_theme/__init__.py", "exec"), namespace)
        rows = namespace["_full_deck_tree_payload"]()
        self.assertEqual({row["did"]: row["done"] for row in rows}, {1: 10, 2: 5, 3: 3, 4: 4})


if __name__ == "__main__":
    unittest.main()
