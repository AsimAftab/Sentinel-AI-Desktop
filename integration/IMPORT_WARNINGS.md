# IDE Import Warnings - Explanation

## Why These Warnings Appear

Your IDE shows import warnings for `src.utils` modules in `backend_runner.py`. **These warnings are expected and harmless.** Here's why:

### The Situation

```python
# backend_runner.py line 222
from src.utils import wake_word_listener  # type: ignore
```

### Why IDE Shows Error

The IDE performs **static analysis** before the code runs:
- ❌ IDE doesn't see `src.utils` in the current project structure
- ❌ IDE doesn't know that `sys.path` will be modified at runtime
- ❌ IDE doesn't know the working directory will change

### Why Code Works at Runtime

The imports work perfectly when the code **actually runs** because:
1. ✅ `sys.path` is modified to include backend directory (line 110)
2. ✅ Working directory is changed to backend directory (line 133)
3. ✅ Imports happen **AFTER** these path changes
4. ✅ Python finds the modules at runtime

### The Fix

Added `# type: ignore` comments to tell the IDE:
> "I know this looks wrong, but trust me - it works at runtime"

```python
from src.utils import wake_word_listener  # type: ignore
from src.utils import speech_recognizer  # type: ignore
from src.utils import langgraph_router  # type: ignore
from src.utils.orchestrator import run_sentinel_agent  # type: ignore
```

## psutil Import Warning

```python
# backend_runner.py line 89
import psutil  # type: ignore
```

**psutil is an optional dependency** for process priority management:
- ✅ If installed: Sets backend thread to low priority
- ✅ If not installed: Continues normally without priority adjustment
- ✅ The code handles both cases gracefully

### To Install psutil (Optional)

```bash
pip install psutil
```

This will improve UI responsiveness by deprioritizing the backend thread, but it's not required.

## Summary

| Import | Status | Action |
|--------|--------|--------|
| `src.utils` modules | Runtime imports | Already fixed with `# type: ignore` |
| `psutil` | Optional dependency | Already fixed with `# type: ignore` |

**All imports are working correctly at runtime.** The IDE warnings are just static analysis limitations.
