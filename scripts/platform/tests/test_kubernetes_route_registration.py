"""Static route registration guard; catches the historical concatenated-path defect."""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps/control-plane/src/opsproof_control/kubernetes_operations.py"


class TestRouterPathContract(unittest.TestCase):
    def test_all_declared_router_suffixes_start_with_slash(self):
        module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        paths = []
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == "router"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    paths.append(decorator.args[0].value)
        self.assertGreaterEqual(len(paths), 4, "Expected to find Kubernetes API routes")
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("/"), f"Missing route separator: {path}")


if __name__ == "__main__":
    unittest.main()
