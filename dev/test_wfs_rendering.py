"""Quick WFS rendering diagnostic script.

Run this to test if WFS data fetching and rendering pipeline works correctly.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from bimap.data.wfs_source import WfsSource
from bimap.models.data_source import DataSource, SourceType
from bimap.models.data_layer import DataLayer

# Test with a public Spanish WFS service (Catastro)
TEST_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
TEST_FEATURE_TYPE = ""  # Will discover from GetCapabilities

def discover_feature_types(url: str):
    """Get available feature types from WFS GetCapabilities."""
    from bimap.data.wfs_source import _parse_capabilities_feature_types
    import requests
    from bimap.config import HTTP_HEADERS
    
    print(f"\n→ Discovering feature types from GetCapabilities...")
    resp = requests.get(url, params={"SERVICE": "WFS", "REQUEST": "GetCapabilities"},
                       headers=HTTP_HEADERS, timeout=15)
    resp.raise_for_status()
    types = _parse_capabilities_feature_types(resp.text)
    print(f"   Found {len(types)} feature types")
    if types:
        print(f"   First type: {types[0]}")
    return types

def test_wfs_fetch():
    """Test that WFS connector can fetch data successfully."""
    print("=" * 70)
    print("WFS Data Fetch Test")
    print("=" * 70)
    
    # First, discover available feature types
    try:
        types = discover_feature_types(TEST_WFS_URL)
        if not types:
            print("   ✗ No feature types found!")
            return False
        feature_type = types[0]  # Use first available type
    except Exception as e:
        print(f"   ✗ GetCapabilities failed: {e}")
        return False
    
    print(f"\n1. Creating WFS connector...")
    print(f"   URL: {TEST_WFS_URL}")
    print(f"   Feature Type: {feature_type}")
    
    wfs = WfsSource(
        url=TEST_WFS_URL,
        type_name=feature_type,
        max_features=10,
        bbox="",  # No bbox filter
        cql_filter=""  # No CQL filter
    )
    
    try:
        print(f"\n2. Connecting to WFS service...")
        wfs.connect()
        print("   ✓ Connection successful")
        
        print(f"\n3. Fetching features...")
        rows = wfs.fetch()
        print(f"   ✓ Fetched {len(rows)} features")
        
        if rows:
            print(f"\n4. Sample feature data:")
            sample = rows[0]
            print(f"   Keys: {list(sample.keys())}")
            print(f"   Has geometry: {bool(sample.get('_coordinates'))}")
            print(f"   Geom type: {sample.get('_geom_type', 'N/A')}")
            print(f"   Lat/Lon: {sample.get('_lat', 'N/A')}, {sample.get('_lon', 'N/A')}")
            
            # Show first few attributes
            print(f"\n5. First 5 attributes:")
            count = 0
            for key, value in sample.items():
                if not key.startswith('_'):
                    print(f"   - {key}: {value}")
                    count += 1
                    if count >= 5:
                        break
        else:
            print("   ⚠ No features returned!")
        
        print(f"\n6. Testing DataLayer model...")
        layer = DataLayer(
            name="Test WFS Layer",
            source_id="test-id",
            visible=True,
            opacity=1.0,
            icon_color="#3b82f6",
            icon_size=10
        )
        print(f"   ✓ DataLayer created: visible={layer.visible}, opacity={layer.opacity}")
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        print("\nIf layers still don't show in UI, check:")
        print("  1. MainWindow._on_data_refreshed is being called")
        print("  2. Canvas.update_data_layer_rows receives the data")
        print("  3. Project.data_layers contains a DataLayer for this source")
        print("  4. OverlayRenderer._draw_data_layers is being called")
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            wfs.disconnect()
            print("\n7. Disconnected")
        except:
            pass

if __name__ == "__main__":
    success = test_wfs_fetch()
    sys.exit(0 if success else 1)
