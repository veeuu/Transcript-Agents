# Lazy import to avoid triggering module-level side effects on package load
def run_pipeline(text: str, save_output: bool = True):
    from .pipeline import run_pipeline as _run
    return _run(text, save_output)
