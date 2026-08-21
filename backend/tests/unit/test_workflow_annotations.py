"""
Tests for canvas annotations (the Note step).

A note is a comment the workflow author leaves for whoever edits it next. The
engine has no handler for one, so every code path that reasons about the flow
has to know it is not a step — otherwise adding a comment to a workflow breaks
it: validation reports an unsupported step type, the builder warns that it is
unconnected (it always is), or the executor trips over one reached through a
hand-built edge.
"""
import pytest


class TestAnnotations:
    """
    Notes live on the canvas but never run.

    The engine has no handler for a note, so anything that treats one as a step
    turns a comment into a broken workflow: validation reporting an unsupported
    step type, a warning that it is unconnected (it always is), or an executor
    that trips over one reachable through a hand-built edge.
    """

    def test_a_note_is_an_annotation(self):
        from app.services.workflows.graph import is_annotation

        assert is_annotation("note") is True
        assert is_annotation("speak") is False
        assert is_annotation("trigger") is False
        assert is_annotation(None) is False

    def test_a_note_is_not_reported_as_an_unsupported_step(self):
        from app.services.workflows.graph import validate_graph

        graph = {
            "nodes": [
                {"id": "t", "type": "trigger", "name": "Start", "config": {}},
                {
                    "id": "s",
                    "type": "speak",
                    "name": "Say hi",
                    "config": {"message": "hi"},
                },
                {
                    "id": "n",
                    "type": "note",
                    "name": "Note",
                    "config": {"text": "ask billing first"},
                },
            ],
            "edges": [{"id": "e", "source": "t", "target": "s"}],
        }

        result = validate_graph(graph)
        assert result["errors"] == []

    def test_a_note_is_not_warned_about_for_being_unconnected(self):
        from app.services.workflows.graph import validate_graph

        graph = {
            "nodes": [
                {"id": "t", "type": "trigger", "name": "Start", "config": {}},
                {
                    "id": "s",
                    "type": "speak",
                    "name": "Say hi",
                    "config": {"message": "hi"},
                },
                {"id": "n", "type": "note", "name": "Note", "config": {}},
            ],
            "edges": [{"id": "e", "source": "t", "target": "s"}],
        }

        warnings = validate_graph(graph)["warnings"]
        assert not [w for w in warnings if w["nodeId"] == "n"]

    def test_an_unknown_step_type_is_still_an_error(self):
        """The annotation exemption must not become a hole for typos."""
        from app.services.workflows.graph import validate_graph

        graph = {
            "nodes": [
                {"id": "t", "type": "trigger", "name": "Start", "config": {}},
                {"id": "x", "type": "notes", "name": "Typo", "config": {}},
            ],
            "edges": [{"id": "e", "source": "t", "target": "x"}],
        }

        errors = validate_graph(graph)["errors"]
        assert any(e["nodeId"] == "x" for e in errors)


class TestExecutorSkipsAnnotations:
    """
    A note reached through an edge passes through instead of failing the run.

    The builder gives notes no handles, so nothing can normally connect one.
    But a graph posted through the API can point an edge anywhere, and "your
    workflow died on a comment" is a baffling way to discover that.
    """

    @staticmethod
    def _graph():
        return {
            "schema_version": 2,
            "nodes": [
                {"id": "t", "type": "trigger", "name": "Start", "config": {}},
                {"id": "n", "type": "note", "name": "Note", "config": {"text": "hi"}},
                {"id": "s", "type": "speak", "name": "Say hi", "config": {}},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "t",
                    "sourceHandle": "out",
                    "target": "n",
                    "targetHandle": "in",
                },
                {
                    "id": "e2",
                    "source": "n",
                    "sourceHandle": "out",
                    "target": "s",
                    "targetHandle": "in",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_the_note_never_reaches_a_handler(self):
        from app.services.workflows.executor import GraphExecutor, NodeOutcome

        ran = []

        async def run_node(node):
            ran.append(node["id"])
            return NodeOutcome(status="success", result={}, handles=["out"])

        executor = GraphExecutor(graph=self._graph(), run_node=run_node)
        results, counts = await executor.run()

        # There is no handler for a note; reaching one would raise.
        assert "n" not in ran
        assert counts["failed"] == 0

        by_id = {r["step_id"]: r for r in results}
        assert by_id["n"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_the_step_after_a_note_still_runs(self):
        """A note must pass control on, not swallow the rest of the branch."""
        from app.services.workflows.executor import GraphExecutor, NodeOutcome

        ran = []

        async def run_node(node):
            ran.append(node["id"])
            return NodeOutcome(status="success", result={}, handles=["out"])

        executor = GraphExecutor(graph=self._graph(), run_node=run_node)
        await executor.run()

        assert "s" in ran
