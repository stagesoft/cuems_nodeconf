# Cuems NodeConf Test Suite

Comprehensive test suite for cuems-nodeconf covering all major functionality.

## Test Structure

### Test Files

1. **`test_interface_detection.py`** - Network interface detection tests
   - Interface detection with mocked interfaces
   - Priority handling (bridge0:avahi vs ethernet1:avahi)
   - Timeout handling

2. **`test_avahi_listener.py`** - Avahi/Zeroconf service listener tests
   - Service addition/update/removal
   - IP address selection logic
   - Error handling for invalid service info
   - Property validation

3. **`test_communicate.py`** - Communication thread tests
   - Thread initialization
   - Stop flag functionality (verifies bug fix)

4. **`test_nodeconf_comprehensive.py`** - Comprehensive CuemsNodeConf tests
   - Initialization
   - Node type determination (master/slave/firstrun)
   - Network map operations (read/write/merge)
   - Node adoption/unadoption
   - Missing node detection
   - Engine callback handling
   - Service discovery
   - Error handling
   - NodeDict properties

5. **`test_integration.py`** - End-to-end integration tests
   - First-run becomes master scenario
   - Slave discovers master scenario
   - Node adoption workflow
   - Master/slave network merge

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_nodeconf_comprehensive.py

# Run specific test class
pytest tests/test_nodeconf_comprehensive.py::TestNodeAdoption

# Run specific test
pytest tests/test_nodeconf_comprehensive.py::TestNodeAdoption::test_adopt_node_success

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## Test Coverage

### Core Functionality
- ✅ Network interface detection and prioritization
- ✅ IP address validation and error handling
- ✅ Node type determination (master/slave/firstrun)
- ✅ Service discovery and registration
- ✅ Local node retrieval

### Network Map Operations
- ✅ Reading network map from XML
- ✅ Writing network map to XML
- ✅ Merging discovered nodes with existing map
- ✅ Preserving adopted status during merge
- ✅ Marking nodes as online/offline

### Node Management
- ✅ Node adoption
- ✅ Node unadoption
- ✅ Master node protection (cannot unadopt)
- ✅ Missing adopted node detection
- ✅ Master always adopted logic
- ✅ First-run adoption behavior

### Communication
- ✅ Engine callback handling
- ✅ Adopt/unadopt via callback
- ✅ Error handling in callbacks
- ✅ Thread management

### Error Handling
- ✅ Network interface timeout
- ✅ Missing IP address handling
- ✅ Invalid service info handling
- ✅ Missing properties handling

### Integration Scenarios
- ✅ First-run node becomes master
- ✅ Slave node discovers master
- ✅ Complete adoption workflow
- ✅ Master/slave network merge

## Test Fixtures

The `conftest.py` file provides:
- **`mock_netifaces`** - Automatically mocks network interfaces for all tests
  - Provides `bridge0:avahi` (169.254.1.1)
  - Provides `ethernet1:avahi` (169.254.2.1)
  - Provides `bond0` (192.168.1.100)

## Notes

- All tests use mocked network interfaces, so they can run without actual network hardware
- Tests are isolated and don't require system services (Avahi, systemd, etc.)
- File operations use temporary directories via pytest's `tmp_path` fixture
- External operations (DBus, subprocess, file I/O) are mocked where appropriate

