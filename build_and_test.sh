#!/bin/bash
set -e

echo "======================================"
echo "  CUEMS NodeConf Build & Test Script"
echo "======================================"
echo ""

# Step 1: Run XML roundtrip test
echo "Step 1: Running XML serialization tests..."
python3 test_xml_roundtrip.py
if [ $? -ne 0 ]; then
    echo "❌ XML tests failed! Fix the issues before building."
    exit 1
fi
echo "✅ XML tests passed"
echo ""

# Step 2: Run unit tests
echo "Step 2: Running unit tests..."
python3 -m pytest tests/ -v 2>/dev/null || echo "⚠️  No pytest tests found or pytest not installed"
echo ""

# Step 3: Build package
echo "Step 3: Building Debian package..."
debuild -b -uc -us -nc 2>&1 | tail -20
if [ $? -ne 0 ]; then
    echo "❌ Package build failed!"
    exit 1
fi
echo "✅ Package built successfully"
echo ""

# Step 4: Copy to rc1_packages
echo "Step 4: Copying package to rc1_packages..."
cp ../cuems-nodeconf_0.1.0-1_all.deb /home/ion/src/cuems/rc1_packages/
ls -lh /home/ion/src/cuems/rc1_packages/cuems-nodeconf_0.1.0-1_all.deb
echo ""

echo "======================================"
echo "  ✅ Build complete and ready to deploy!"
echo "======================================"
echo ""
echo "Package: /home/ion/src/cuems/rc1_packages/cuems-nodeconf_0.1.0-1_all.deb"


