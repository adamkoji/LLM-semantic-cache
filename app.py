import os

try:
    import spaces

    @spaces.GPU
    def _zerogpu_probe():
        return "ok"
except Exception:
    spaces = None

import uvicorn
from api.main import app

if __name__ == "__main__":
    if spaces is not None:
        try:
            from spaces import zero as _spaces_zero
            if hasattr(_spaces_zero, "startup"):
                _spaces_zero.startup()
                print("[app] ZeroGPU startup report sent successfully", flush=True)
        except Exception as err:
            print(f"[app] ZeroGPU startup hook skipped: {err}", flush=True)

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 7860)))
