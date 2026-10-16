"""Exercise both release modes through the actual Streamlit application."""

from pathlib import Path

import torch
from streamlit.testing.v1 import AppTest

from pharmasentinel.io import write_json


def main():
    torch.set_num_threads(2)
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(root / "ui/app.py"), default_timeout=120).run()
    results = {}
    for name in ("pharmasentinel_final", "biomedbert_all_ce"):
        app.sidebar.selectbox[0].set_value(name).run()
        for page in ("Dataset", "Model quality", "Review analysis", "Try a passage"):
            app.sidebar.radio[0].set_value(page).run()
            assert not app.exception, [e.value for e in app.exception]
            assert not app.warning, [e.value for e in app.warning]
        app.button[0].click().run()
        assert not app.exception, [e.value for e in app.exception]
        assert len(app.get("download_button")) == 1
        results[name] = {"four_pages_passed": True, "live_extraction_download": True}
    write_json(root / "reports/verification/viewer_preflight.json", results)
    print(results)


if __name__ == "__main__":
    main()
