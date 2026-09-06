"""Run explicitly with Playwright installed. All network requests stay offline."""
import json
import mimetypes
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location("shards", ROOT / "scripts/build_history_shards.py")
    shards = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shards)
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as playwright:
        generated = Path(directory).resolve()
        for dataset in ("dynasty_player_trajectories", "player_rank_trajectories"):
            shards.write_history_shards(generated, dataset, json.loads((ROOT / f"data/{dataset}.json").read_text()))
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script("localStorage.setItem('oracle_adv_unlocked', '1')")
        requests, errors = [], []
        def serve(route):
            parts = urlsplit(route.request.url)
            if parts.hostname != "audit.invalid" or route.request.method != "GET":
                route.abort()
                return
            relative = unquote(parts.path).lstrip("/")
            requests.append(relative)
            path = (generated / relative).resolve()
            if not path.is_relative_to(generated) or not path.is_file():
                path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT) and not path.is_relative_to(generated):
                route.abort()
            elif not path.is_file():
                route.fulfill(status=404, body="Not found")
            else:
                route.fulfill(status=200, content_type=mimetypes.guess_type(path)[0] or "application/octet-stream", body=path.read_bytes())
        context.route("**/*", serve)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        cdp = context.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        started = time.monotonic()
        page.goto("https://audit.invalid/dynasty_rankings.html")
        page.wait_for_function("document.querySelectorAll('#tableBody tr').length === 200")
        initial_ms = round((time.monotonic() - started) * 1000)
        nodes = page.locator("*").count()
        cells = page.locator("#tableBody tr").first.locator("td").count()
        assert page.locator("#tableBody .col-advanced").count() == 0
        page.locator("#btnAdvanced").click()
        assert page.locator("#tableBody tr").first.locator("td").count() > cells
        page.locator("#btnSimple").click()
        page.locator("#tableBody .pin-btn").first.click()
        assert page.locator("#tableBody .row-pinned").count() == 1
        page.locator("#posFilter").select_option("SP")
        assert page.locator('#tableBody [data-stat-type="bat"]').count() == 0
        page.locator("#posFilter").select_option("all")
        started = time.monotonic()
        page.locator("#searchInput").fill("Soto")
        page.wait_for_function("document.querySelectorAll('#tableBody tr:not(.pin-sep)').length < 20")
        search_ms = round((time.monotonic() - started) * 1000)
        with page.expect_response(lambda response: "/data/history/dynasty_player_trajectories/" in response.url):
            page.locator("#tableBody .player-link").first.click()
        page.wait_for_selector("#playerModal.open")
        page.wait_for_selector("#playerModalChart circle")
        page.keyboard.press("Escape")
        assert page.locator("#playerModal").get_attribute("aria-hidden") == "true"
        assert any(path.startswith("data/history/dynasty_player_trajectories/") for path in requests)
        assert "data/dynasty_player_trajectories.json" not in requests
        page.goto("https://audit.invalid/dynasty_rankings.html?search=Juan%20Soto")
        page.wait_for_function("document.querySelector('#searchInput').value === 'Juan Soto'")
        for name, selector in [("roster_depth.html", ".pill[data-player-key]:visible"),
                               ("prospects.html", ".player-detail-button[data-player-name]:visible")]:
            page.goto("https://audit.invalid/" + name)
            if name == "prospects.html":
                page.locator("#tab-radar").click()
            page.locator(selector).first.click()
            page.wait_for_selector("#playerModal.open")
            page.wait_for_timeout(300)
            page.keyboard.press("Escape")
            assert page.locator("#playerModal").get_attribute("aria-hidden") == "true"
        assert "data/player_rank_trajectories.json" not in requests
        assert page.evaluate("['','juan soto','josé','大谷'].map(k => PlayerHistory.bucketFor(k,64))") == [5, 26, 39, 50]
        assert not errors, errors
        print(json.dumps({"rankings_nodes": nodes, "simple_cells": cells,
                          "initial_4x_cpu_ms": initial_ms, "search_4x_cpu_ms": search_ms,
                          "browser_errors": errors}))
        browser.close()


if __name__ == "__main__":
    main()
