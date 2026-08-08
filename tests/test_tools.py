"""Sanity tests for the standalone tool modules. Run with: pytest -q"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.task_manager import TaskManager
from tools.filesystem import FileSystemTools


def test_filesystem_read_write_list():
    with tempfile.TemporaryDirectory() as tmp:
        fs = FileSystemTools(tmp)
        fs.write_file("src/hello.py", "print('hi')\n")
        assert fs.read_file("src/hello.py") == "print('hi')\n"
        assert "src/hello.py" in fs.list_files()


def test_filesystem_blocks_path_escape():
    with tempfile.TemporaryDirectory() as tmp:
        fs = FileSystemTools(tmp)
        try:
            fs.read_file("../../etc/passwd")
            assert False, "should have raised ValueError"
        except ValueError:
            pass


def test_task_manager_context_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        tm = TaskManager(tmp)
        tm.write_architecture("# Architecture\nSome notes.")
        tm.append_decision("Keep it simple")
        context = tm.read_context()
        assert "Some notes" in context
        assert "Keep it simple" in context


def test_task_manager_tasks_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        tm = TaskManager(tmp)
        tasks = [{"id": 1, "title": "Do X"}]
        tm.save_tasks(tasks)
        assert tm.load_tasks() == tasks
