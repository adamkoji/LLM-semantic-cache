import os
import uvicorn

try:
    import spaces

    @spaces.GPU
    def _zerogpu_health_probe():
        return "ok"
except ImportError:
    pass

from api.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 7860)))
