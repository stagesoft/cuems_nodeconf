<!--
***
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# cuems-nodeconf

**Current release: development (unreleased)** — see [CHANGELOG.md](./CHANGELOG.md).

**Zeroconf-based node discovery and role-assignment module for the CueMS distributed show-control system.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.kernel.org/)

- **Source / issues:** [stagesoft/cuems-nodeconf](https://github.com/stagesoft/cuems-nodeconf) on GitHub

`cuems-nodeconf` is a Python module embedded as a git submodule inside
[cuems-engine](https://github.com/stagesoft/cuems-engine). It runs at boot time
to discover every CueMS node on the local network via mDNS/Zeroconf (Avahi), assign
each node a role — **master** or **slave** — and persist the resulting topology as an
XML network map consumed by the engine. Once its work is done it exits with a
machine-readable status code that the calling service can act on.

It is composed of:

- **`CuemsNodeConf`** — main orchestrator: bootstraps Zeroconf, determines role,
  writes the network map, and terminates with an exit code.
- **`CuemsAvahiListener`** — `zeroconf.ServiceListener` implementation that maintains
  a live `CuemsNodeDict` of all discovered peers.
- **`CuemsNode` / `CuemsNodeDict`** — lightweight data structures representing a
  single network node and a typed, role-indexed collection thereof.
- **`CuemsSettings`** — helper that derives the local node's identity (IP, MAC,
  hostname) from the active network interface.
- **`CuemsConfServer`** — experimental TCP server for inter-node configuration
  exchange (work in progress).
- **`AvahiTool`** — standalone command-line diagnostic utility for monitoring all
  CueMS Zeroconf services on the network.
- **System integration files** — Avahi service XML templates, sudoers rules, Avahi
  daemon configuration, and ACPI power-button scripts.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [CuemsNodeConf](#cuemsnodeconf)
  - [CuemsAvahiListener](#cuemsavahilistener)
  - [CuemsNode and CuemsNodeDict](#cuemsnode-and-cuemsnodedict)
  - [CuemsSettings](#cuemssettings)
  - [CuemsConfServer](#cuemsconfserver)
  - [AvahiTool](#avahitool)
  - [System Integration Files](#system-integration-files)
  - [Threading and Process Model](#threading-and-process-model)
- [Core Concepts](#core-concepts)
- [Design Goals](#design-goals)
- [API Documentation](#api-documentation)
  - [Zeroconf Services](#zeroconf-services)
  - [Network Map XML](#network-map-xml)
  - [Master Lock File](#master-lock-file)
  - [Process Exit Codes](#process-exit-codes)
  - [TCP Configuration Protocol](#tcp-configuration-protocol)
- [Installation](#installation)
  - [As a git submodule](#as-a-git-submodule)
  - [System dependencies](#system-dependencies)
  - [Configuration files](#configuration-files)
- [Usage](#usage)
- [Development](#development)
- [Contributors](#contributors)
- [Release notes](#release-notes)
- [Future developments](#future-developments)
  - [Automated test suite](#automated-test-suite)
  - [CI — tests and coverage workflow](#ci--tests-and-coverage-workflow)
  - [Documentation site](#documentation-site)
  - [Packaging and deployment](#packaging-and-deployment)
  - [Target badge set](#target-badge-set)
- [Copyright notice](#copyright-notice)
- [License](#license)

---

[↑ Back to Table of Contents](#table-of-contents)

## Overview

`cuems-nodeconf` runs once per boot, discovers its peers on the local network using
mDNS (via the Avahi daemon and the `zeroconf` Python library), negotiates a
master/slave topology, and writes a shared network map. The diagram below shows the
full execution flow:

```
  Node boots (called by cuems-engine or systemd)
      │
      ▼
  CuemsNodeConf.__init__()
      │
      ├──► 1. Load configuration  (/etc/cuems/nodeconf.xml  via ConfigManager)
      │
      ├──► 2. Start mDNS browser  (_cuems_nodeconf._tcp.local.)
      │               CuemsAvahiListener ◄──── mDNS announcements from LAN peers
      │                    └── populates CuemsNodeDict (keyed by MAC address)
      │
      ├──► 3. Identify self  (match local IP against discovered nodes)
      │
      ├──► 4. Role assignment  (only when service file contains node_type=firstrun)
      │          No master on LAN  ──►  become MASTER
      │                                   sudo cp cuems.service.master
      │                                   → /etc/avahi/services/cuems.service
      │                                   avahi-publish -aR master.local <ip>
      │          Master present   ──►  stay SLAVE
      │                                   sudo cp cuems.service.slave
      │                                   → /etc/avahi/services/cuems.service
      │
      ├──► 5. Wait for any firstrun peers to complete their own role assignment
      │
      ├──► 6. Validate topology  (check_nodes — at least one master required)
      │
      ├──► 7. Write /etc/cuems/network_map.xml  (XSD-validated via XmlWriter)
      │
      ├──► 8. Update /etc/cuems/master.lock
      │             master present  ──►  create file
      │             slave           ──►  remove file (if it exists)
      │
      └──► sys.exit(100)  ← this node is master
           sys.exit(101)  ← this node is slave
```

Each step is non-optional; a failure before step 6 raises an exception and the
calling service interprets a non-100/101 exit as a configuration error.

---

[↑ Back to Table of Contents](#table-of-contents)

## Architecture

### CuemsNodeConf

**File:** `CuemsNodeConf.py`

The top-level orchestrator. Instantiated once by the engine; its `__init__` drives
the entire node-configuration sequence and terminates the process when complete.

| Symbol | Role |
|---|---|
| **`CuemsNodeConf`** | Orchestrates discovery, role assignment, map writing, and process exit. |
| `CuemsNodeConf.get_ip()` | Static helper — returns the IPv4 address of the default-route interface. |
| `CuemsNodeConf.start_avahi_listener()` | Creates a `CuemsAvahiListener` and a `zeroconf.ServiceBrowser`, then waits 2 s for initial announcements. |
| `CuemsNodeConf.retreive_local_node()` | Polls `listener.nodes` up to three times (0.5 s apart) to find the entry whose IP matches the local IP; raises if not found. |
| `CuemsNodeConf.set_node_type()` | Checks whether a master already exists; assigns the role and copies the matching Avahi service template via `sudo cp`. |
| `CuemsNodeConf.publish_master_alias()` | Spawns `avahi-publish -aR master.local <ip>` as a background process so that other nodes can resolve the master by hostname. |
| `CuemsNodeConf.check_nodes()` | Validates that at least one master is present in `listener.nodes`; logs slave count. |
| `CuemsNodeConf.write_network_map()` | Serialises `listener.nodes` to `/etc/cuems/network_map.xml` using `XmlWriter` against `network_map.xsd`. |
| `CuemsNodeConf.read_network_map()` | Deserialises `/etc/cuems/network_map.xml` back into a `CuemsNodeDict` (used in tests/debugging). |
| `CuemsNodeConf.update_master_lock_file()` | Creates `/etc/cuems/master.lock` when this node is master; removes it otherwise. |
| `CuemsNodeConf.cleanup()` | Removes the engine's show-lock file on teardown. |

**Key constants (module-level):**

| Constant | Value | Purpose |
|---|---|---|
| `CUEMS_CONF_PATH` | `/etc/cuems/` | Root for all runtime configuration files. |
| `MAP_SCHEMA_FILE` | `network_map.xsd` | XSD schema for the network map (bundled in this repo). |
| `MAP_FILE` | `network_map.xml` | Output network map path. |
| `CUEMS_SERVICE_TEMPLATES_PATH` | `/usr/share/cuems/` | Installed location for Avahi service template files. |
| `CUEMS_SERVICE_FILE` | `cuems.service` | Avahi service file written to `/etc/avahi/services/`. |
| `CUEMS_MASTER_LOCK_FILE` | `master.lock` | Sentinel file present only on the master node. |

---

### CuemsAvahiListener

**File:** `CuemsAvahiListener.py`

Implements `zeroconf.ServiceListener`. Receives add/update/remove callbacks from
`ServiceBrowser` and maintains a class-level `CuemsNodeDict` that is shared across
all instances (by design — only one listener is ever created per process).

| Symbol | Role |
|---|---|
| **`CuemsAvahiListener`** | Zeroconf `ServiceListener` that builds and maintains the live node registry. |
| `CuemsAvahiListener.nodes` | Class-level `CuemsNodeDict` (keyed by MAC address); holds all currently visible peers. |
| `CuemsAvahiListener.Action` | Enum with values `ADD`, `UPDATE`, `DELETE`; passed to the optional callback. |
| `CuemsAvahiListener.get_mac()` | Extracts the 12-character MAC prefix from an Avahi service name. |
| `CuemsAvahiListener.add_service()` | Queries full `ServiceInfo`, constructs a `CuemsNode`, and inserts it into `nodes`. |
| `CuemsAvahiListener.update_service()` | Re-queries `ServiceInfo` and calls `dict.update()` on the existing `CuemsNode` entry. |
| `CuemsAvahiListener.remove_service()` | Fires the optional callback with `Action.DELETE` (node is not removed from the dict — this is intentional: the node may still be reachable). |

The `_cuems_nodeconf._tcp.local.` service TXT records are decoded from bytes and
used to populate each `CuemsNode`:

```
b"node_type"  →  CuemsNode.NodeType enum member
b"uuid"       →  string UUID
```

---

### CuemsNode and CuemsNodeDict

**File:** `CuemsNode.py`

Minimal data structures for node representation.

| Symbol | Role |
|---|---|
| **`CuemsNode`** | `dict` subclass with typed property accessors for all node fields. |
| `CuemsNode.NodeType` | `enum.Enum` with values `slave=0`, `master=1`, `firstrun=2`. |
| `CuemsNode.uuid` | String UUID identifying the node service instance. |
| `CuemsNode.mac` | 12-character hex MAC address; used as the primary dictionary key in `CuemsNodeDict`. |
| `CuemsNode.name` | Full Avahi service name (e.g. `<MAC> Cuems node on <hostname>._cuems_nodeconf._tcp.local.`). |
| `CuemsNode.node_type` | `NodeType` enum member reflecting the current role. |
| `CuemsNode.ip` | IPv4 address string as reported by Zeroconf. |
| `CuemsNode.port` | TCP port integer. |
| **`CuemsNodeDict`** | `dict` subclass (keyed by MAC) with computed, role-filtered list properties. |
| `CuemsNodeDict.masters` | Read-only property — list of all `CuemsNode` entries with `node_type == master`. |
| `CuemsNodeDict.slaves` | Read-only property — list of all `CuemsNode` entries with `node_type == slave`. |
| `CuemsNodeDict.firstruns` | Read-only property — list of all `CuemsNode` entries with `node_type == firstrun`. |

---

### CuemsSettings

**File:** `CuemsSettings.py`

A collection of standalone helper functions for reading local node identity. Used
primarily by `CuemsConfServer` and test scripts.

| Symbol | Role |
|---|---|
| `get_ip()` | Returns the IPv4 address of the default-route network interface. |
| `read_conf()` | Assembles a settings dictionary with `ip`, `uuid` (currently the MAC with a prefix), `hostname`, `server`, `type_`, `name`, `port`, `properties`, `host_ttl`, and `other_ttl`. |

> **Note:** `read_conf()` contains a documented temporary workaround (`TEMP FIXX`) that
> substitutes the MAC address for a proper UUID. This will be replaced once the engine
> exposes a stable per-node UUID.

---

### CuemsConfServer

**File:** `CuemsConfServer.py`

An experimental TCP configuration server based on `socketserver.TCPServer`. Intended
to let slave nodes pull their runtime configuration from the master; currently returns
placeholder data.

| Symbol | Role |
|---|---|
| **`CuemsConfServer`** | `socketserver.TCPServer` subclass; binds on the address provided by the caller. |
| **`CuemsConfServerHandler`** | `socketserver.BaseRequestHandler` subclass; dispatches incoming requests by keyword. |
| `CuemsConfServerHandler.handle()` | Reads up to 1 024 bytes; replies with an ACK string (on `Hello`) or a JSON payload (on `Conf`). |

> **Status:** work in progress. The `Conf` response body is a hardcoded placeholder
> and is not yet wired to any real configuration source.

---

### AvahiTool

**File:** `AvahiTool.py`

A standalone diagnostic command-line tool. Run directly (`python3 AvahiTool.py`) to
watch all CueMS Zeroconf service events on the network until a key is pressed.

| Symbol | Role |
|---|---|
| **`AvahiTool`** | Wrapper that creates a `Zeroconf` instance and a `MyAvahiListener` for both `_cuems_nodeconf._tcp.local.` and `_cuems_osc._tcp.local.`. |
| **`MyAvahiListener`** | Service listener that pretty-prints every add/update/remove event and the current node table. |
| `NodeType` | Module-local enum mirroring `CuemsNode.NodeType` (used for display only). |
| `AvahiTool.shutdown()` | Closes the `Zeroconf` instance gracefully. |

`AvahiTool` is not imported by any other module in this package; it is an operator
utility only.

---

### System Integration Files

| File | Role |
|---|---|
| `cuems.service.master` | Avahi service XML template for a master node; publishes `_cuems_nodeconf._tcp` on port 9000 and `_cuems_osc._tcp` on port 9090 with `node_type=master`. |
| `cuems.service.slave` | Avahi service XML template for a slave node; same ports, `node_type=slave`. |
| `cuems.service.firstrun` | Avahi service XML template for a not-yet-configured node; `node_type=firstrun`. Copied to `/etc/avahi/services/cuems.service` on a fresh image. |
| `network_map.xsd` | XSD schema (namespace `http://stagelab.net/cuems`) defining `CuemsNetworkMap > CuemsNodeDict > CuemsNode` with mandatory fields: `uuid`, `mac`, `name`, `node_type`, `ip`, `port`. |
| `sudoers.d.cuems.conf` | Grants the `cuems` system user passwordless `cp` of the three service templates into `/etc/avahi/services/` and passwordless `systemctl reload avahi-daemon`. |
| `avahi-daemon.conf` | Reference Avahi daemon configuration: IPv4-only, mDNS, `ratelimit-burst=1000`. |
| `power_button/cuems-power-button-waiter.sh` | Waits 3 seconds after a single power-button press before allowing the `powerbtn-custom-handler.sh` to proceed. |
| `power_button/powerbtn-custom-handler.sh` | ACPI event handler: single press schedules a 1-minute shutdown; double press cancels shutdown, resets the Avahi service file to `firstrun`, and reboots into auto-configuration mode. |
| `power_button/powerbtn-acpi-support` | ACPI event binding file (`event=power (PBTN)`) that routes power-button events to `powerbtn-custom-handler.sh`. |
| `power_button/power-button-setup.txt` | Installation notes for the ACPI power-button integration. |

---

### Threading and Process Model

`cuems-nodeconf` is a **short-lived process**, not a daemon. It runs to completion and
exits. The concurrency model is minimal:

- The `Zeroconf` object runs its own internal I/O threads for mDNS packet processing.
- `ServiceBrowser` fires callbacks (`add_service`, `update_service`, `remove_service`)
  from the Zeroconf I/O thread into `CuemsAvahiListener`.
- The main thread waits with `time.sleep()` calls at two points: after starting the
  browser (2 s) and while there are firstrun peers outstanding (0.5 s polling loop).
- `publish_master_alias()` spawns `avahi-publish` as a separate OS process with
  `subprocess.Popen(..., close_fds=True)`; it outlives the Python process by design.
- `CuemsConfServer` (when used in test scripts) is run in a daemon thread via
  `threading.Thread(daemon=True)`, so it does not block process exit.

---

[↑ Back to Table of Contents](#table-of-contents)

## Core Concepts

- **Node role** — every CueMS node on a LAN is either `master`, `slave`, or `firstrun`.
  `firstrun` is a transient bootstrap state; a node enters `firstrun` when its Avahi
  service file has `node_type=firstrun` (e.g. on a freshly imaged node or after a
  power-button reset). It resolves to `master` or `slave` within seconds.

- **Zeroconf / mDNS** — node discovery is fully zero-configuration: no static IP lists,
  no central registry. Each node announces itself on the LAN via the Avahi daemon using
  the service type `_cuems_nodeconf._tcp.local.`; peers discover each other
  automatically.

- **MAC as primary key** — `CuemsNodeDict` uses the 12-character hex MAC address as
  the dictionary key. MAC is extracted directly from the Avahi service name and is
  stable across reboots, making it a reliable identity anchor.

- **Service template swap** — role assignment is persisted by copying a pre-written
  Avahi service XML file (`cuems.service.master` or `cuems.service.slave`) over the
  live Avahi service file (`/etc/avahi/services/cuems.service`). Avahi picks up the
  change automatically and re-broadcasts with the new `node_type` TXT record.

- **Network map** — the master and all slaves write `/etc/cuems/network_map.xml`, an
  XSD-validated snapshot of all nodes discovered during the configuration run. The
  engine reads this file to know which nodes are available and what roles they hold.

- **master.lock** — a sentinel file at `/etc/cuems/master.lock`. Its presence (or
  absence) lets shell scripts and other processes determine the local node's role
  without parsing the XML map or querying Avahi.

- **Exit code contract** — `cuems-nodeconf` signals its result exclusively through
  `sys.exit(100)` (master) or `sys.exit(101)` (slave). The calling service
  (`cuems-engine` or a systemd `ExecStartPost`) reads this value and branches
  accordingly. Any other exit code indicates an error.

- **Submodule design** — `cuems-nodeconf` is intentionally a git submodule rather than
  a standalone package. It imports `ConfigManager` and `XmlReaderWriter` from the
  parent `cuems-engine` package using relative imports (`from ..ConfigManager import …`),
  keeping node-configuration logic separate while sharing engine infrastructure.

---

[↑ Back to Table of Contents](#table-of-contents)

## Design Goals

- **Zero-configuration topology** — no administrator action is required to bring a new
  node into a CueMS network. Plug it in, boot it, and `cuems-nodeconf` handles
  everything.

- **Single-master guarantee** — if no master exists when a node starts, that node
  becomes master. If a master already exists, the new node becomes slave. The 2-second
  listening window before role negotiation ensures that a race between two
  simultaneously-booting nodes is resolved deterministically.

- **Idempotent re-entry** — a node that has already been configured as master or slave
  (i.e. its Avahi service file already has a non-`firstrun` `node_type`) skips role
  assignment entirely and proceeds directly to network-map generation.

- **Process-exit signalling** — using `sys.exit(100|101)` rather than writing a role
  file or setting an environment variable means the result is immediately available to
  any POSIX-aware caller (systemd `SuccessExitStatus`, shell `$?`, Python
  `subprocess.run().returncode`).

- **Power-button reset path** — operators can force a node back into `firstrun` mode by
  pressing the power button twice within 3 seconds. This copies `cuems.service.firstrun`
  over the live service file and reboots, without requiring SSH access or physical media.

- **Principle of least privilege** — the only operations that require elevated rights
  (copying service template files, reloading Avahi) are listed explicitly in
  `sudoers.d.cuems.conf`. The `cuems` user cannot sudo anything else.

- **Schema-validated persistence** — the network map is written through `XmlWriter`
  against `network_map.xsd`, ensuring that a corrupt or incomplete map is rejected at
  write time rather than silently accepted and causing downstream failures in the engine.

---

[↑ Back to Table of Contents](#table-of-contents)

## API Documentation

`cuems-nodeconf` does not expose an HTTP, REST, or library API. Its external surface
consists of the Zeroconf services it publishes and consumes, the files it writes, and
the exit codes it uses to signal results.

---

### Zeroconf Services

Both service types use IPv4 only (`protocol="ipv4"` in the Avahi XML).

#### `_cuems_nodeconf._tcp.local.` — node-configuration service

Published by every CueMS node via the Avahi daemon (not by Python directly).

| Field | Value | Notes |
|---|---|---|
| Service type | `_cuems_nodeconf._tcp.local.` | Browsed by `CuemsAvahiListener` and `AvahiTool`. |
| Port | `9000` | TCP; used by the experimental `CuemsConfServer`. |
| TXT `node_type` | `master` \| `slave` \| `firstrun` | Decoded with `b"node_type"` key. |
| TXT `uuid` | UUID string | Decoded with `b"uuid"` key; used as a secondary identifier alongside MAC. |
| Service name format | `<MAC12> Cuems node on <hostname>._cuems_nodeconf._tcp.local.` | The 12-character MAC prefix is extracted by `CuemsAvahiListener.get_mac()`. |

#### `_cuems_osc._tcp.local.` — OSC communication service

Published by the Avahi daemon alongside the nodeconf service (same templates).

| Field | Value | Notes |
|---|---|---|
| Service type | `_cuems_osc._tcp.local.` | Published for discovery by OSC-aware components; not consumed by `cuems-nodeconf` itself. Browsed by `AvahiTool`. |
| Port | `9090` | TCP (OSC over TCP). |
| TXT `node_type` | `master` \| `slave` \| `firstrun` | Mirrors the nodeconf service TXT record. |
| TXT `uuid` | UUID string | Same UUID as the nodeconf service. |

#### `master.local` — master-node hostname alias

When this node becomes master, `CuemsNodeConf.publish_master_alias()` calls:

```
avahi-publish -a -R master.local <ip>
```

This creates an additional mDNS A record so that any host on the LAN can resolve
`master.local` to the master node's IP without knowing its hardware hostname.

---

### Network Map XML

Written to `/etc/cuems/network_map.xml` after every successful node-configuration run.
The schema is defined in `network_map.xsd` (namespace `http://stagelab.net/cuems`).

```xml
<CuemsNetworkMap>
  <CuemsNodeDict>
    <CuemsNode>
      <uuid>0367f391-ebf4-48b2-9f26-aabbccddeeff</uuid>
      <mac>aabbccddeeff</mac>
      <name>aabbccddeeff Cuems node on hostname._cuems_nodeconf._tcp.local.</name>
      <node_type>master</node_type>
      <ip>192.168.1.10</ip>
      <port>9000</port>
    </CuemsNode>
    <!-- one <CuemsNode> per discovered peer -->
  </CuemsNodeDict>
</CuemsNetworkMap>
```

All elements are mandatory (`minOccurs="1"`) and non-empty (enforced by the
`NonEmptyString` simple type restriction). The `<CuemsNodeDict>` wrapper is optional
(`minOccurs="0"`) to allow an empty map.

---

### Master Lock File

**Path:** `/etc/cuems/master.lock`

A zero-content sentinel file. `CuemsNodeConf.update_master_lock_file()` creates it if
(and only if) the local node is master, and removes it if the local node is slave.

| State | File present | File absent |
|---|---|---|
| Local node role | master | slave |

Scripts and services can test for the master role with a simple file existence check:

```bash
test -f /etc/cuems/master.lock && echo "I am master" || echo "I am slave"
```

---

### Process Exit Codes

`CuemsNodeConf.__init__` always terminates the process via `sys.exit()`.

| Code | Meaning |
|---|---|
| `100` | This node completed configuration as **master**. |
| `101` | This node completed configuration as **slave**. |
| Any other code | Error during configuration (exception propagated). |

systemd example (`cuems-engine.service`):

```ini
[Service]
ExecStart=/path/to/python3 -m cuems_engine
SuccessExitStatus=100 101
```

---

### TCP Configuration Protocol

> **Status: experimental / work in progress.** The server is not activated in the
> production `CuemsNodeConf` path; it appears only in the `test_run_nodeconfig.py`
> test script.

`CuemsConfServer` listens on `<hostname>.local.:9000` (TCP). The protocol is
line-less and keyword-triggered:

| Client sends | Server replies |
|---|---|
| Any bytes containing `Hello` | `ACK <address>, slave node with uuid: <uuid>` |
| Any bytes containing `Conf` | JSON object (currently a placeholder payload) |

The maximum request size is 1 024 bytes per `recv()` call; there is no framing.

---

[↑ Back to Table of Contents](#table-of-contents)

## Installation

`cuems-nodeconf` is not a standalone installable package. It is a git submodule of
[cuems-engine](https://github.com/stagesoft/cuems-engine) and is installed as part of
that project.

### As a git submodule

When cloning `cuems-engine`, initialize this submodule with:

```bash
git clone --recurse-submodules https://github.com/stagesoft/cuems-engine.git
```

If you already have a clone without submodules:

```bash
git submodule update --init --recursive
```

To work on `cuems-nodeconf` independently:

```bash
git clone https://github.com/stagesoft/cuems-nodeconf.git
```

Note that standalone use requires the parent `cuems-engine` package to be importable
(for `ConfigManager` and `XmlReaderWriter`), or those imports must be shimmed for
testing.

### System dependencies

The following system packages must be present on the target Linux host:

| Package | Purpose |
|---|---|
| `avahi-daemon` | mDNS/Zeroconf daemon that broadcasts the node's service records. |
| `avahi-utils` | Provides the `avahi-publish` binary used for the `master.local` alias. |
| `python3-zeroconf` | Python Zeroconf library (`zeroconf` package); used for service browsing. |
| `python3-netifaces` | Network interface introspection (`netifaces` package). |
| `acpid` | ACPI event daemon; required for power-button script integration. |

Install on Debian/Ubuntu:

```bash
sudo apt-get install avahi-daemon avahi-utils python3-zeroconf python3-netifaces acpid
```

### Configuration files

Place the following files on the target node:

| Source file | Target path | Notes |
|---|---|---|
| `cuems.service.firstrun` | `/usr/share/cuems/cuems.service.firstrun` | Copied to Avahi services dir on fresh boot. |
| `cuems.service.master` | `/usr/share/cuems/cuems.service.master` | Template for master role. |
| `cuems.service.slave` | `/usr/share/cuems/cuems.service.slave` | Template for slave role. |
| `network_map.xsd` | `/etc/cuems/network_map.xsd` | Schema for network-map validation. |
| `sudoers.d.cuems.conf` | `/etc/sudoers.d/cuems` | Passwordless service-file copy for the `cuems` user. |
| `avahi-daemon.conf` | `/etc/avahi/avahi-daemon.conf` | Reference Avahi configuration. |

For power-button integration:

```bash
sudo cp power_button/powerbtn-acpi-support /etc/acpi/events/powerbtn-acpi-support
sudo cp power_button/powerbtn-custom-handler.sh /etc/acpi/
sudo cp power_button/cuems-power-button-waiter.sh /etc/acpi/
sudo chmod +x /etc/acpi/powerbtn-custom-handler.sh /etc/acpi/cuems-power-button-waiter.sh
```

Disable the default systemd power-button handler to prevent conflicts:

```ini
# /etc/systemd/logind.conf
HandlePowerKey=ignore
```

---

[↑ Back to Table of Contents](#table-of-contents)

## Usage

`cuems-nodeconf` is designed to be invoked by `cuems-engine` at startup, not run
directly by operators. The engine calls:

```python
from cuems_nodeconf.CuemsNodeConf import CuemsNodeConf
CuemsNodeConf()   # blocks until exit(100) or exit(101)
```

After the call returns (it never does — `sys.exit()` terminates the process), the
engine reads the result from the OS exit code and from the files written to
`/etc/cuems/`.

**Diagnostic utility** — to inspect all CueMS Zeroconf services on the network in
real time, run `AvahiTool` directly:

```bash
cd /path/to/cuems-nodeconf
python3 AvahiTool.py
```

Output example:

```
Cuems Avahi Tool - StageLab Coop
This little tool will show all the CUEMS avahi zeroconf services
on the net and their changes when they appear, update or disappear
It will end when you press a key.
________________________________________________________________________
This is the list of services we are looking for: ['_cuems_nodeconf._tcp.local.',
'_cuems_osc._tcp.local.']

________________________________________________________________________
Service ADDED
Name : aabbccddeeff Cuems node on hostname._cuems_nodeconf._tcp.local.
SERVICE: _cuems_nodeconf._tcp.local.
UUID: 0367f391-ebf4-48b2-9f26-aabbccddeeff
MAC: aabbccddeeff
Node type: NodeType.master
IP: 192.168.1.10
Port: 9000
…
```

Press any key to exit `AvahiTool`.

**Power-button reset** — to force a node back into `firstrun` auto-configuration mode
without SSH access: press the power button once, then press it again within 3 seconds.
The node will cancel the pending shutdown, reset the Avahi service file to `firstrun`,
and reboot.

---

[↑ Back to Table of Contents](#table-of-contents)

## Development

`cuems-nodeconf` has no build system and no automated test suite yet (see
[Future developments](#future-developments)). The `test_run_*.py` scripts in the repo
root are manual integration scripts intended to be run against a live Avahi daemon.

### Set up a development environment

```bash
# Clone standalone (for isolated work)
git clone https://github.com/stagesoft/cuems-nodeconf.git
cd cuems-nodeconf

# Install Python dependencies
pip install zeroconf netifaces

# Ensure Avahi is running with the appropriate service file
sudo systemctl start avahi-daemon
```

### Run the integration test scripts

```bash
# Requires a live Avahi daemon and a published _cuems_nodeconf._tcp.local. service
python3 test_run_nodeconfig.py

# Standalone node-config + TCP server test
python3 test_run_classes.py
```

> These scripts register a Zeroconf service, wait for peers, and print the discovered
> topology. They are **not** unit tests — they require a real LAN with at least one
> Avahi-advertising CueMS node (or a second terminal running the other script).

### Code style

There is no enforced formatter or linter currently. Contributions should follow PEP 8.
`ruff check .` is the recommended linter for new work (see
[Future developments](#future-developments)).

### Branching

All contributions target the `main` branch via pull request. See
[CONTRIBUTORS.md](./CONTRIBUTORS.md) for the full contributing workflow.

---

[↑ Back to Table of Contents](#table-of-contents)

## Contributors

Contributions are welcome. Please read [CONTRIBUTORS.md](./CONTRIBUTORS.md) for the
full contributing workflow, which covers:

- Development prerequisites and setup
- Contribution tiers (trivial vs. non-trivial changes)
- Branch naming conventions
- Spec-first requirement for non-trivial changes
- TDD workflow
- Conventional Commits v1.0 and DCO sign-off
- Pull request requirements and acceptance criteria
- Review process (Ion Reguera [@ibiltari](https://github.com/ibiltari) and
  Adrià Masip [@backenv](https://github.com/backenv))

---

[↑ Back to Table of Contents](#table-of-contents)

## Release notes

There are no tagged releases yet. All development has taken place on a single branch
since January 2021. The full commit history is in [CHANGELOG.md](./CHANGELOG.md).

**Early architecture (January 2021):** The initial commits established a server/client
structure for master and slave nodes using `socketserver.TCPServer`, alongside the
first `CuemsAvahiListener` and node-state enum. The module was then refactored to
remove the hard-coded server/client split and integrate as a submodule of
`cuems-engine`.

**Network map and role assignment (February–March 2021):** The XSD-validated
`network_map.xml` output was introduced, driven by `XmlWriter` from the engine.
Avahi service template files (`cuems.service.master`, `cuems.service.slave`,
`cuems.service.firstrun`) replaced the earlier approach of dynamically constructing
`ServiceInfo` objects. Sudoers rules were added to allow the `cuems` user to copy
templates without a password. The `Present` field was removed from both the Python
objects and the XSD schema.

**Avahi and OSC services (April 2021 — early):** OSC service entries
(`_cuems_osc._tcp`) were added to all three Avahi service template files. The
`AvahiTool` diagnostic utility was extended to browse both service types. UUID and MAC
fields were added to `CuemsNode` and the Avahi TXT records. The `master.local` mDNS
alias was implemented via `avahi-publish`. Power-button ACPI scripts were completed.

**Exit codes and lock file (April 2021 — late):** Integer exit codes 100 (master) and
101 (slave) replaced string-based signalling. The master lock file
(`/etc/cuems/master.lock`) was introduced as a lightweight role sentinel. The power
button scripts were updated to reference `cuems.service` and `cuems.service.firstrun`
by their final installed names. A bug was fixed where the `update_service` callback
used the UUID instead of the MAC as the dictionary key.

---

[↑ Back to Table of Contents](#table-of-contents)

## Future developments

The following items are planned but not yet implemented. They are described here so
they can be wired in incrementally.

### Automated test suite

`cuems-nodeconf` has no unit tests. The two `test_run_*.py` scripts are manual
integration scripts that require a live Avahi environment. The planned approach is:

- Extract all network-I/O calls (Zeroconf, `netifaces`, `subprocess`) behind
  injectable interfaces so that unit tests can mock them.
- Write `pytest` unit tests for `CuemsNodeConf`, `CuemsAvahiListener`,
  `CuemsNode`, and `CuemsNodeDict`, achieving at minimum 80 % line coverage.
- Add `pytest` and `pytest-cov` as development dependencies.

### CI — tests and coverage workflow

Once a test suite exists, a GitHub Actions workflow at
`.github/workflows/tests.yml` should run on every push to `main` and on every pull
request:

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install system dependencies
        run: sudo apt-get install -y avahi-daemon avahi-utils
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install Python dependencies
        run: pip install zeroconf netifaces pytest pytest-cov
      - name: Run tests with coverage
        run: pytest --cov=. --cov-report=xml
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: false
        env:
          CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

**One-time manual step:** activate the repository at
[codecov.io/gh/stagesoft/cuems-nodeconf](https://codecov.io/gh/stagesoft/cuems-nodeconf)
after the first successful workflow run.

### Documentation site

A MkDocs-based documentation site should be generated and deployed to GitHub Pages via
a `.github/workflows/gh-pages.yml` workflow. The `mkdocs.yml` should set:

```yaml
site_name: cuems-nodeconf
repo_url: https://github.com/stagesoft/cuems-nodeconf
```

The `mkdocstrings` plugin (with the Python handler) can generate API reference pages
from docstrings once the source modules have been annotated.

### Packaging and deployment

A Debian package (`cuems-nodeconf_*.deb`) should install:

- The Python module files to the appropriate site-packages path.
- The Avahi service templates to `/usr/share/cuems/`.
- `network_map.xsd` to `/etc/cuems/`.
- `sudoers.d.cuems.conf` to `/etc/sudoers.d/cuems`.
- The ACPI scripts to `/etc/acpi/`.
- A systemd service unit that invokes `cuems-nodeconf` at boot with
  `SuccessExitStatus=100 101`.

### Target badge set

Once each pipeline is live, add the following badges to the top of this README:

```markdown
[![Tests](https://github.com/stagesoft/cuems-nodeconf/actions/workflows/tests.yml/badge.svg)](https://github.com/stagesoft/cuems-nodeconf/actions/workflows/tests.yml)
[![Coverage](https://codecov.io/gh/stagesoft/cuems-nodeconf/graph/badge.svg)](https://codecov.io/gh/stagesoft/cuems-nodeconf)
[![Deploy MkDocs site](https://github.com/stagesoft/cuems-nodeconf/actions/workflows/gh-pages.yml/badge.svg)](https://github.com/stagesoft/cuems-nodeconf/actions/workflows/gh-pages.yml)
```

---

[↑ Back to Table of Contents](#table-of-contents)

## Copyright notice

`cuems-nodeconf` — Zeroconf node discovery and role-assignment module for CueMS.

Copyright (C) 2026 Stagelab Coop SCCL

This program is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this
program. If not, see <https://www.gnu.org/licenses/>.

> **Note on bundled third-party files:** `avahi-daemon.conf` is derived from the
> default Avahi daemon configuration file, which is distributed under the GNU Lesser
> General Public License v2.1 or later. The Avahi project is not affiliated with
> Stagelab Coop SCCL.

---

[↑ Back to Table of Contents](#table-of-contents)

## License

This project is licensed under the **GNU General Public License v3.0 or later**
(SPDX: `GPL-3.0-or-later`).

See [LICENSE](./LICENSE) for the full licence text.
