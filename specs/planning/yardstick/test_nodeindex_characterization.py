"""Characterization tests for ``NodeIndex`` (T037-T041) — research E23, R7.

Pinned against ``cuems-nodeconf/cuemsnodeconf/CuemsNodeConf.py``'s current
behaviour (``merge_discovered_nodes`` :440, ``_map_signature`` :281,
``adopt_node``/``unadopt_node`` :516/:537, ``set_master_always_adopted`` :490,
``check_missing_adopted_nodes`` :501), read from that repository on disk at
``/disk/Projects/StageLab/cuems-nodeconf`` — **not imported**: the daemon
module's top-level imports (``zeroconf``, ``netifaces``, ``systemd.daemon``,
``dbus``) are not available in this project's environment, and are exactly the
dependency this port exists to leave behind (SC-009). Each test's docstring
names the source lines its expectation was read from, so the pin is
verifiable by inspection even though it cannot be executed against the
original.

Written **before** ``NodeIndex.merge``/``adopt``/etc. existed, and each fails
against an empty implementation (``AttributeError: 'NodeIndex' object has no
attribute 'merge'``) — the fail-then-pass discipline E23 asks for, applied to
code this repository does not own yet.
"""

from __future__ import annotations

from cuemsutils.config.network_map import node
from cuemsutils.tools.NodeList import NodeIndex, NodeRole


def _node(**kwargs):
    defaults = {
        "uuid": None, "mac": None, "name": None, "node_role": NodeRole.node,
        "ip": None, "adopted": False, "online": False,
    }
    defaults.update(kwargs)
    return node(defaults)


# --- merge_discovered_nodes (CuemsNodeConf.py:440) --------------------------


def test_merge_matches_by_uuid_not_mac():
    """:440-482 — matched by uuid; the mac key of an existing entry is never
    replaced by the discovered node's mac (the controller-duplication bug the
    comment at :442-449 records)."""
    existing = NodeIndex({
        "aa:existing": _node(uuid="u1", mac="aa:existing", name="old-name",
                              node_role=NodeRole.controller, ip="10.0.0.1",
                              adopted=True, online=False, role_id="r1"),
    })
    discovered = NodeIndex({
        "controller": _node(uuid="u1", mac="controller", name="new-name",
                             node_role=NodeRole.controller, ip="10.0.0.2"),
    })

    existing.merge(discovered)

    assert set(existing.keys()) == {"aa:existing"}
    merged = existing["aa:existing"]
    assert merged["mac"] == "aa:existing"          # never clobbered
    assert merged["name"] == "new-name"             # discovery field refreshed
    assert merged["ip"] == "10.0.0.2"
    assert merged["adopted"] is True                # preserved, not overwritten
    assert merged["online"] is True
    assert merged["role_id"] == "r1"                # operator field untouched


def test_merge_adds_a_genuinely_new_node_keyed_by_its_own_mac():
    """:475-482 — a node with no uuid match is added, keyed by its own mac,
    ``adopted=False``, ``online=True``."""
    existing = NodeIndex()
    discovered = NodeIndex({
        "bb:new": _node(uuid="u2", mac="bb:new", name="fresh"),
    })

    existing.merge(discovered)

    assert set(existing.keys()) == {"bb:new"}
    assert existing["bb:new"]["adopted"] is False
    assert existing["bb:new"]["online"] is True


def test_merge_marks_undiscovered_existing_nodes_offline():
    """:484-488 — the offline pass, keyed on uuid."""
    existing = NodeIndex({
        "cc:gone": _node(uuid="u3", mac="cc:gone", online=True),
    })
    existing.merge(NodeIndex())

    assert existing["cc:gone"]["online"] is False


# --- _map_signature (CuemsNodeConf.py:281) -----------------------------------


def test_signature_is_stable_regardless_of_insertion_order():
    """:281-293 — sorted by key, so two indexes with the same content in a
    different order agree."""
    a = NodeIndex({
        "aa": _node(uuid="u1", mac="aa"),
        "bb": _node(uuid="u2", mac="bb"),
    })
    b = NodeIndex({
        "bb": _node(uuid="u2", mac="bb"),
        "aa": _node(uuid="u1", mac="aa"),
    })
    assert a.signature() == b.signature()


def test_signature_changes_when_a_persisted_field_changes():
    idx = NodeIndex({"aa": _node(uuid="u1", mac="aa", adopted=False)})
    before = idx.signature()
    idx["aa"]["adopted"] = True
    assert idx.signature() != before


# --- adopt_node / unadopt_node (CuemsNodeConf.py:516, :537) ------------------


def test_adopt_refuses_an_offline_node():
    """:524-527 — offline is refused."""
    idx = NodeIndex({"aa": _node(uuid="u1", mac="aa", online=False, adopted=False)})
    assert idx.adopt("u1") is False
    assert idx["aa"]["adopted"] is False


def test_adopt_succeeds_when_online():
    idx = NodeIndex({"aa": _node(uuid="u1", mac="aa", online=True, adopted=False)})
    assert idx.adopt("u1") is True
    assert idx["aa"]["adopted"] is True


def test_adopt_is_idempotent_when_already_adopted():
    """:519-522 — already-adopted is a no-op success, even offline."""
    idx = NodeIndex({"aa": _node(uuid="u1", mac="aa", online=False, adopted=True)})
    assert idx.adopt("u1") is True


def test_adopt_of_an_unknown_node_fails():
    assert NodeIndex().adopt("nope") is False


def test_unadopt_refuses_the_controller():
    """:540-542 — the controller-unadopt refusal."""
    idx = NodeIndex({
        "aa": _node(uuid="u1", mac="aa", node_role=NodeRole.controller, adopted=True),
    })
    assert idx.unadopt("u1") is False
    assert idx["aa"]["adopted"] is True


def test_unadopt_a_non_controller_succeeds_even_offline():
    """:549-552 — offline nodes can and should be unadoptable."""
    idx = NodeIndex({
        "aa": _node(uuid="u1", mac="aa", node_role=NodeRole.node,
                    adopted=True, online=False),
    })
    assert idx.unadopt("u1") is True
    assert idx["aa"]["adopted"] is False


def test_unadopt_is_idempotent_when_already_unadopted():
    idx = NodeIndex({
        "aa": _node(uuid="u1", mac="aa", node_role=NodeRole.node, adopted=False),
    })
    assert idx.unadopt("u1") is True


# --- set_master_always_adopted (CuemsNodeConf.py:490) ------------------------


def test_set_controller_always_adopted_adopts_every_controller():
    """:491-494. The daemon's first-run-clears-others branch (:496-499) is
    not ported — see ``CuemsNetworkMapType.refresh``'s docstring and
    ``migration-guide.md``."""
    idx = NodeIndex({
        "aa": _node(uuid="u1", mac="aa", node_role=NodeRole.controller, adopted=False),
        "bb": _node(uuid="u2", mac="bb", node_role=NodeRole.node, adopted=False),
    })
    idx.set_controller_always_adopted()
    assert idx["aa"]["adopted"] is True
    assert idx["bb"]["adopted"] is False  # untouched — no first-run clearing


# --- check_missing_adopted_nodes (CuemsNodeConf.py:501) ----------------------


def test_missing_adopted_reports_adopted_nodes_not_currently_discovered():
    """:501-514 — adopted nodes whose uuid is not among the discovered ones."""
    idx = NodeIndex({
        "aa": _node(uuid="u1", mac="aa", adopted=True),
        "bb": _node(uuid="u2", mac="bb", adopted=True),
        "cc": _node(uuid="u3", mac="cc", adopted=False),
    })
    discovered = NodeIndex({"aa": _node(uuid="u1", mac="aa")})

    missing = idx.missing_adopted(discovered)

    assert len(missing) == 1
    assert missing[0]["uuid"] == "u2"


def test_missing_adopted_is_empty_when_all_adopted_nodes_are_present():
    idx = NodeIndex({"aa": _node(uuid="u1", mac="aa", adopted=True)})
    discovered = NodeIndex({"aa": _node(uuid="u1", mac="aa")})
    assert idx.missing_adopted(discovered) == ()
