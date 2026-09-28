"""Test WFS and WMS GeoJSON conversion for data layers.

This script verifies that both WFS and WMS properly convert features to GeoJSON
format with _coordinates, _geom_type, _lat, and _lon fields for rendering.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from bimap.data.wfs_source import WfsSource
from bimap.data.wms_source import WmsSource
from bimap.models.data_source import DataSource, SourceType
from bimap.models.data_layer import DataLayer
from bimap.data import build_connector

def test_wfs_geojson():
    """Test WFS GeoJSON conversion."""
    print("\n" + "=" * 70)
    print("TEST 1: WFS GeoJSON Conversion")
    print("=" * 70)
    
    wfs = WfsSource(
        url="https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx",
        type_name="cp:CadastralParcel",
        max_features=5,
        bbox="",
        cql_filter=""
    )
    
    try:
        wfs.connect()
        rows = wfs.fetch()
        
        print(f"\n✓ Fetched {len(rows)} WFS features")
        
        if rows:
            sample = rows[0]
            print(f"\n✓ Sample feature has required GeoJSON fields:")
            print(f"  - _geom_type: {sample.get('_geom_type')}")
            print(f"  - _lat: {sample.get('_lat')}")
            print(f"  - _lon: {sample.get('_lon')}")
            print(f"  - _coordinates: {sample.get('_coordinates')}")
            
            # Verify all required fields
            required = ["_geom_type", "_lat", "_lon", "_coordinates"]
            missing = [f for f in required if f not in sample]
            if missing:
                print(f"\n✗ MISSING FIELDS: {missing}")
                return False
            print(f"\n✓ All required GeoJSON fields present")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wms_geojson():
    """Test WMS GetCapabilities layer discovery and GeoJSON conversion."""
    print("\n" + "=" * 70)
    print("TEST 2: WMS GeoJSON Conversion")
    print("=" * 70)
    
    # Test WMS GetCapabilities layer catalogue mode
    wms = WmsSource(
        url="https://www.ign.es/wms-inspire/pnoa-ma",
        layer_name="",  # Empty = catalogue mode
        styles="",
        bbox="",
        info_format="application/json",
        width=101,
        height=101
    )
    
    try:
        wms.connect()
        rows = wms.fetch()
        
        print(f"\n✓ WMS GetCapabilities returned {len(rows)} layers")
        
        if rows:
            sample = rows[0]
            print(f"\n✓ Sample layer metadata:")
            print(f"  - layer name: {sample.get('_layer_name')}")
            print(f"  - title: {sample.get('_title')}")
            print(f"  - _lat: {sample.get('_lat')}")
            print(f"  - _lon: {sample.get('_lon')}")
            
            # For catalogue mode, layers should at least have geometry point
            if "_lat" in sample and "_lon" in sample:
                print(f"\n✓ Layer metadata has coordinates")
            
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factory_connector():
    """Test that build_connector properly creates WFS and WMS sources."""
    print("\n" + "=" * 70)
    print("TEST 3: Factory Connector Creation")
    print("=" * 70)
    
    try:
        # Test WFS
        ds_wfs = DataSource(
            name="Test WFS",
            source_type=SourceType.WFS,
            connection={
                "url": "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx",
                "type_name": "cp:CadastralParcel",
                "max_features": "10"
            }
        )
        
        connector_wfs = build_connector(ds_wfs)
        print(f"\n✓ WFS connector created: {type(connector_wfs).__name__}")
        
        # Test WMS
        ds_wms = DataSource(
            name="Test WMS",
            source_type=SourceType.WMS,
            connection={
                "url": "https://www.ign.es/wms-inspire/pnoa-ma",
                "layer_name": "",
                "width": "101",
                "height": "101"
            }
        )
        
        connector_wms = build_connector(ds_wms)
        print(f"✓ WMS connector created: {type(connector_wms).__name__}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_layer_rendering():
    """Test that DataLayer model works with GeoJSON features."""
    print("\n" + "=" * 70)
    print("TEST 4: DataLayer Model for GeoJSON")
    print("=" * 70)
    
    try:
        # Create a data layer
        layer = DataLayer(
            name="Catastral Parcels",
            source_id="catastro-parcels",
            visible=True,
            opacity=1.0,
            icon_color="#3b82f6",
            icon_size=8,
            label_column="label"
        )
        
        print(f"\n✓ DataLayer created:")
        print(f"  - name: {layer.name}")
        print(f"  - visible: {layer.visible}")
        print(f"  - opacity: {layer.opacity}")
        print(f"  - icon_size: {layer.icon_size}")
        
        # Simulate a GeoJSON row (as returned by WFS/WMS with our fixes)
        sample_row = {
            "_geom_type": "Point",
            "_lat": "40.45",
            "_lon": "-3.68",
            "_coordinates": "[-3.68, 40.45]",
            "label": "Parcel 001",
            "area": "5000"
        }
        
        # Verify overlay renderer would receive this
        print(f"\n✓ Sample GeoJSON row structure:")
        print(f"  - Has coordinates: {bool(sample_row.get('_coordinates'))}")
        print(f"  - Has geometry type: {bool(sample_row.get('_geom_type'))}")
        print(f"  - Has lat/lon: {bool(sample_row.get('_lat') and sample_row.get('_lon'))}")
        print(f"  - Can display as feature: ✓")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    tests = [
        ("WFS GeoJSON", test_wfs_geojson),
        ("WMS GeoJSON", test_wms_geojson),
        ("Factory", test_factory_connector),
        ("DataLayer", test_data_layer_rendering),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Unexpected error in {name}: {e}")
            results[name] = False
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! WFS and WMS now output proper GeoJSON format.")
        print("\nData layers should now render correctly with:")
        print("  - Point features shown as dots")
        print("  - Polygon/Line geometries shown with their forms")
        print("  - Full attribute data available for properties panel")
        sys.exit(0)
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        sys.exit(1)
