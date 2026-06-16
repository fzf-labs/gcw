from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / ".gcw" / "engine" / "runtime"
HOSTED = ROOT / ".gcw" / "engine" / "hosted"
PLATFORMS = ROOT / ".gcw" / "engine" / "platforms"
SKILL_SCRIPTS = ROOT / ".agents" / "skills" / "gcw" / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"
GITLAB_CI = ROOT / ".gitlab-ci.yml"


def python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.py") if path.name != "__pycache__")


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def subprocess_commands(path: Path) -> list[str]:
    commands: list[str] = []
    for node in ast.walk(parse(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_subprocess_call = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
            and func.attr in {"run", "check_output", "call", "Popen"}
        )
        if not is_subprocess_call or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.List):
            values = []
            for item in first.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    values.append(item.value)
            commands.extend(values[:1])
    return commands


class ImportBoundaryTest(unittest.TestCase):
    def test_runtime_is_self_contained(self) -> None:
        for path in python_files(RUNTIME):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(".agents/", text, msg=str(path))
            self.assertNotIn(".agents", text, msg=str(path))
            self.assertNotIn(".gcw/engine/hosted", text, msg=str(path))
            self.assertNotIn(".gcw/scripts", text, msg=str(path))

    def test_runtime_does_not_shell_out_to_platform_clis(self) -> None:
        forbidden = {"gh", "glab", "git"}
        for path in python_files(RUNTIME):
            self.assertTrue(forbidden.isdisjoint(subprocess_commands(path)), msg=str(path))

    def test_hosted_scripts_are_the_only_ci_entrypoints(self) -> None:
        for path in sorted(WORKFLOWS.glob("gcw-*.yml")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(".gcw/scripts/", text, msg=path.name)
            if "gcw_workflow_event.py" in text or "prepare_gcw_hosted_step.py" in text:
                self.assertIn(".gcw/engine/hosted/", text, msg=path.name)
        gitlab_text = GITLAB_CI.read_text(encoding="utf-8")
        self.assertIn(".gcw/engine/hosted/", gitlab_text)
        self.assertNotIn(".gcw/scripts/", gitlab_text)

    def test_runtime_modules_do_not_import_skill_script_modules(self) -> None:
        skill_module_names = {path.stem for path in python_files(SKILL_SCRIPTS)}
        for path in python_files(RUNTIME):
            self.assertTrue(imported_modules(path).isdisjoint(skill_module_names), msg=str(path))


if __name__ == "__main__":
    unittest.main()
