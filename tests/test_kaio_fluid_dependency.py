from kaio_fluid.dependency import DependencyCentrality, DependencyNode


def test_dependency_centrality_prioritizes_high_unlock_low_effort_blocker():
    nodes = (
        DependencyNode("A", blocked=True, effort=0.4),
        DependencyNode("B", blocked=True, effort=0.9),
        DependencyNode("C"),
        DependencyNode("D"),
        DependencyNode("E"),
    )
    graph = DependencyCentrality(
        nodes,
        (
            ("A", "C"),
            ("C", "D"),
            ("D", "E"),
            ("B", "E"),
        ),
    )
    ranked = graph.ranked_blockers()
    assert ranked[0][0] == "A"
    assert graph.downstream("A") == ("C", "D", "E")
