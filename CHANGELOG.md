<!--
***
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# Changelog

All notable changes to `cuems-nodeconf` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Commit messages are quoted verbatim where they add precision.

---

## Unreleased — 2021-01-13 → 2021-04-28

No version tag has been cut yet. All changes below represent the complete development
history of the module. They are grouped thematically rather than by individual commit
to show how the design evolved through four distinct phases.

---

### Phase 4 — Exit codes, master lock, and bug fixes  _(2021-04-20 → 2021-04-28)_

Stability and integration fixes prior to first production use.

#### Fixed

- `CuemsAvahiListener.update_service`: the `nodes` dict was being keyed by UUID
  on updates but by MAC on adds, causing a `KeyError` on the first service-update
  event. The key is now consistently the 12-character MAC address extracted by
  `get_mac()`. (commit: `cd840eb`)

- `power_button/powerbtn-custom-handler.sh` and
  `power_button/cuems-power-button-waiter.sh`: scripts referenced stale service-file
  paths; updated to use `cuems.service` and `cuems.service.firstrun` as installed
  under `/usr/share/cuems/`. (commit: `eb356a3`, `1731692`)

#### Added

- Integer exit codes: `sys.exit(100)` for master, `sys.exit(101)` for slave.
  Replaces the earlier approach of exiting with the string `"MASTER"` / `"SLAVE"`.
  Callers (systemd, `cuems-engine`) can now use `SuccessExitStatus=100 101` or
  compare `subprocess.returncode` directly. (commits: `2886e71`, `5badbd2`)

- Master lock file (`/etc/cuems/master.lock`): `CuemsNodeConf.update_master_lock_file()`
  creates this zero-content sentinel when the node is master and removes it otherwise.
  Allows scripts to detect the master role with a simple file-existence check without
  parsing the full network map. (commit: `26dd33a`)

---

### Phase 3 — OSC services, UUID/MAC, master alias, power button  _(2021-04-05 → 2021-04-12)_

Added OSC service advertising, stable node identity via UUID and MAC, the
`master.local` mDNS hostname alias, and the complete ACPI power-button integration.

#### Added

- `_cuems_osc._tcp` service entries added to all three Avahi service template files
  (`cuems.service.master`, `cuems.service.slave`, `cuems.service.firstrun`),
  advertising port 9090. OSC-aware engine components can now discover the master's
  OSC endpoint via mDNS without hard-coded addresses. (commit: `f29437e`)

- `AvahiTool` extended to browse both `_cuems_nodeconf._tcp.local.` and
  `_cuems_osc._tcp.local.`, printing a combined node table on every event.
  (commit: `f29437e`)

- `uuid` TXT record added to all three Avahi service templates. `CuemsAvahiListener`
  now reads both `b"uuid"` and the MAC prefix from the service name, populating the
  corresponding fields on `CuemsNode`. (commits: `a075fae`, `0ef73dd`)

- `CuemsNodeConf.publish_master_alias()`: once a node is confirmed as master it spawns
  `avahi-publish -a -R master.local <ip>` as a detached background process, so other
  nodes can resolve `master.local` regardless of the master's hostname.
  (commit: `222ed2f`)

- `avahi-daemon.conf` reference configuration committed: IPv4-only, mDNS, rate limit
  burst of 1 000 packets/s. (commit: `58dc055`)

- Power-button ACPI scripts completed:
  - `powerbtn-acpi-support` — ACPI event binding for `power (PBTN)`.
  - `powerbtn-custom-handler.sh` — single press schedules a 1-minute shutdown;
    double press (within 3 s) cancels shutdown, resets Avahi service file to
    `firstrun`, and issues an immediate reboot into auto-configuration mode.
  - `cuems-power-button-waiter.sh` — 3-second wait loop used to detect double press.
  - `power-button-setup.txt` — installation notes.
  (commits: `1adb17f`, `a536e7b`)

#### Fixed

- `AvahiTool.remove_service`: node was not being removed from the internal services
  dict on DELETE events. Fixed by calling `self.services.pop(name)` with a
  `KeyError` guard. (commit: `fe4c272`)

- Listing behaviour on node removal: `print_current_present_nodes()` now always
  iterates the full services dict, including when removing, so the display is
  consistent. (commit: `26cfe7e`)

---

### Phase 2 — Role assignment, Avahi templates, network map  _(2021-02-25 → 2021-04-05)_

Replaced the dynamic `ServiceInfo`-based role negotiation with a durable
file-swap mechanism. Introduced the XSD-validated network map and the `firstrun`
concept.

#### Added

- Avahi service template files (`cuems.service.firstrun`, `cuems.service.master`,
  `cuems.service.slave`): pre-written Avahi service XML files installed to
  `/usr/share/cuems/`. Role assignment now copies the appropriate template over
  `/etc/avahi/services/cuems.service` via `sudo cp`, triggering Avahi to re-broadcast
  with the correct `node_type` TXT record. (commit: `723a985`)

- `sudoers.d.cuems.conf`: grants the `cuems` user passwordless `cp` for all three
  templates and passwordless `systemctl reload avahi-daemon`.
  (commits: `77c59a8`, `13c6408`)

- `network_map.xsd`: XSD schema (namespace `http://stagelab.net/cuems`) defining
  `CuemsNetworkMap > CuemsNodeDict > CuemsNode` with mandatory, non-empty elements
  `uuid`, `mac`, `name`, `node_type`, `ip`, `port`. (commit: `1e0b5e3`)

- `CuemsNodeConf.write_network_map()` and `CuemsNodeConf.read_network_map()`:
  serialise and deserialise `CuemsNodeDict` via `XmlWriter` / `XmlReader` from
  `cuems-engine`, validated against the XSD. (commit: `1e0b5e3`)

- `CuemsNodeConf.set_node_type()`: checks `listener.nodes.masters`; if empty,
  assigns `NodeType.master` and copies the master template; otherwise assigns
  `NodeType.slave` and copies the slave template. (commit: `e76dbd9`)

- Wait loop for `firstrun` peers: after role assignment the master waits in a
  0.5-second polling loop until `listener.nodes.firstruns` is empty, ensuring all
  simultaneously-booting nodes complete negotiation before the network map is written.
  (commit: `b29437f`)

- `CuemsNodeConf.publish_master_alias()` stub: initial implementation of the
  `avahi-publish` call (later refined in Phase 3).

#### Changed

- `CuemsNode` and `CuemsNodeDict` overhauled to `dict` subclasses with typed property
  accessors (`uuid`, `mac`, `name`, `node_type`, `ip`, `port`). The earlier dataclass
  approach was removed. (commit: `fe13bbd`)

- Module restructured as a `cuems-engine` submodule: relative imports
  (`from ..ConfigManager import …`, `from ..XmlReaderWriter import …`) replace the
  earlier absolute imports that required standalone execution. (commit: `b6f0c46`)

#### Removed

- `Present` field: removed from `CuemsNode` Python objects (commit: `886cd0f`)
  and from `network_map.xsd` (commit: `6343642`). The field was an artefact of an
  earlier design where nodes could be "present" or "absent" in a persistent map;
  the live-Zeroconf approach makes presence implicit.

#### Fixed

- Slave Avahi service file copy target path corrected from a wrong intermediate
  directory to the canonical `/etc/avahi/services/cuems.service`. (commit: `6847a27`)

- `listener.nodes.master` access: changed from `list[0]` to the correct `dict`
  property accessor after the `CuemsNodeDict` refactor. (commit: `8090cfd`)

---

### Phase 1 — Initial architecture  _(2021-01-13 → 2021-02-23)_

Bootstrapped the module from scratch. Established the Zeroconf service browsing,
node-state enum, and the initial server/client test structure.

#### Added

- `CuemsAvahiListener` (`CuemsAvahiListener.py`): first implementation of the
  `zeroconf.ServiceListener` interface, handling `add_service`, `update_service`,
  and `remove_service` callbacks and maintaining a `CuemsNodeDict`.

- `CuemsNode` and `CuemsNodeDict` (`CuemsNode.py`): data structures for a node
  record and a role-indexed node collection, with `masters`, `slaves`, and
  `firstruns` list properties.

- `CuemsNodeConf` (`CuemsNodeConf.py`): main orchestrator class integrating
  `ConfigManager`, `Zeroconf`, `CuemsAvahiListener`, and `XmlWriter`.

- `CuemsSettings` (`CuemsSettings.py`): `get_ip()` and `read_conf()` helpers to
  derive the local node's identity from the active network interface.

- `CuemsConfServer` (`CuemsConfServer.py`): experimental `socketserver.TCPServer`
  subclass for inter-node configuration exchange.

- `AvahiTool` (`AvahiTool.py`): standalone command-line diagnostic tool for
  monitoring CueMS Zeroconf services.

- `network_map.xsd`: initial XML schema for the network map (later revised to remove
  `Present` and add `uuid`/`mac`).

- `power_button/` scripts: initial ACPI power-button integration for controlled
  shutdown and `firstrun` reset.

- `__init__.py`: empty package marker enabling relative imports from `cuems-engine`.

#### Changed (breaking)

- Server/client architecture refactored: the earlier design where master and slave
  were hard-coded `server` and `client` roles at import time was replaced by runtime
  Zeroconf discovery. (commits: `1c416cb`, `2d22f57`)

---

### Notes

- No version tag has been assigned to any commit. The first tagged release will
  establish the baseline for semantic versioning.
- `CuemsConfServer` and the TCP configuration protocol remain experimental. They are
  not activated in the primary `CuemsNodeConf` code path.
- The `CuemsSettings.read_conf()` function contains a known temporary workaround
  (`# TEMP FIXX`) that uses the MAC address as a UUID substitute. This will be
  resolved when `cuems-engine` exposes a stable per-node UUID to its submodules.
