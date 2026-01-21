#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from app.api import geo
from app.main import app

print("Geo router routes:", [r.path for r in geo.router.routes][:3])
print("Before include - geo routes in app:", len([r for r in app.routes if 'geo' in r.path]))

try:
    app.include_router(geo.router, prefix="/api/v1")
    print("After include - geo routes in app:", len([r for r in app.routes if 'geo' in r.path]))
    print("Sample routes:", [r.path for r in app.routes if 'geo' in r.path][:3])
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

