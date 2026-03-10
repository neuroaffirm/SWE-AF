"""Allow running with ``python -m swe_af``."""

import faulthandler
import sys
import traceback

# Enable fault handler to print tracebacks on crashes/signals
faulthandler.enable()

try:
    from swe_af.app import main
    main()
except SystemExit as e:
    print(f"[SWE-AF] SystemExit: code={e.code}", flush=True)
    traceback.print_exc()
    sys.exit(e.code if e.code is not None else 1)
except Exception as e:
    print(f"[SWE-AF] Fatal startup error: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)
