"""T069: no source file assigns into a ``cuemsutils`` module's namespace.

feature 007 deleted ``cuemsnodeconf/NodeXmlBuilders.py``, whose last four
statements were exactly this pattern — registering custom builders/parsers by
poking them directly into ``cuemsutils.xml.XmlBuilder``'s and
``cuemsutils.xml.Parsers``' module globals (``XmlBuilderModule.node_listXmlBuilder
= node_listXmlBuilder``, and three more like it) so the upstream engine would
pick them up by name. ``cuemsutils`` now has its own public node model and
registry (contract C1, C7); nothing in this repository needs to reach into
another package's namespace to be found. This test asserts the mechanism has
no path back in, not just that the one file that did it is gone.
"""
import ast
import pathlib

import pytest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'cuemsnodeconf'


def _source_files():
    return sorted(PACKAGE_ROOT.glob('*.py'))


def _cuemsutils_module_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to a ``cuemsutils`` (sub)module in this file."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'cuemsutils' or alias.name.startswith('cuemsutils.'):
                    aliases.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == 'cuemsutils' or node.module.startswith('cuemsutils.')):
                # `from cuemsutils.xml import XmlBuilder` binds `XmlBuilder` to
                # the submodule itself, which is just as reachable a target.
                for alias in node.names:
                    aliases.add(alias.asname or alias.name)
    return aliases


def _namespace_injections(tree: ast.Module, module_aliases: set[str]) -> list[str]:
    """Every ``<alias>.<attr> = ...`` assignment targeting one of ``module_aliases``."""
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in module_aliases
            ):
                hits.append(f"{target.value.id}.{target.attr}")
    return hits


class TestNoCuemsutilsNamespaceInjection:
    """No source file in this package assigns an attribute onto an imported
    ``cuemsutils`` module — the mechanism ``NodeXmlBuilders.py`` used."""

    @pytest.mark.parametrize('path', _source_files(), ids=lambda p: p.name)
    def test_file_does_not_inject_into_cuemsutils_namespace(self, path):
        tree = ast.parse(path.read_text(), filename=str(path))
        aliases = _cuemsutils_module_aliases(tree)
        injections = _namespace_injections(tree, aliases)
        assert injections == [], (
            f"{path.name} assigns into a cuemsutils module namespace: {injections}"
        )

    def test_at_least_one_file_imports_cuemsutils(self):
        """Sanity check that the scan above is exercising real imports, not
        silently matching nothing because the glob or the AST walk is broken."""
        found_any = False
        for path in _source_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            if _cuemsutils_module_aliases(tree):
                found_any = True
                break
        assert found_any, "expected at least one cuemsnodeconf module to import cuemsutils"
