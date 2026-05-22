"""URLSearchParams / Headers / FormData mutation coverage.

Items 200-205, 209 of the plan. Verifies the hook flags receiver-typed
mutations on Web API collection values that have non-mutating
alternatives via fresh-instance construction. Also verifies the
suppression marker bypasses each detector and that fresh-instance
patterns pass cleanly.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload

URL_SEARCH_PARAMS_BLOCKED: list[tuple[str, str]] = [
    (
        "const params = new URLSearchParams(query)\nparams.append('q', term)",
        "web-api.url-search-params.append",
    ),
    (
        "const params = new URLSearchParams(query)\nparams.set('q', term)",
        "web-api.url-search-params.set",
    ),
    (
        "const params = new URLSearchParams(query)\nparams.delete('q')",
        "web-api.url-search-params.delete",
    ),
    (
        "const params = new URLSearchParams(query)\nparams.sort()",
        "web-api.url-search-params.sort",
    ),
    (
        "function build(p: URLSearchParams) { p.append('k', 'v') }",
        "web-api.url-search-params.append",
    ),
]


@pytest.mark.parametrize(("snippet", "detector"), URL_SEARCH_PARAMS_BLOCKED)
def test_url_search_params_mutation_blocked(run_hook, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/url.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"unexpected exit {code}\n{stderr}"
    assert detector in stderr, f"detector {detector} missing in:\n{stderr}"


URL_SEARCH_PARAMS_ALLOWED: list[str] = [
    "const next = new URLSearchParams([...params, ['q', term]])",
    "const next = new URLSearchParams([...[...params].filter(([k]) => k !== 'q'), ['q', term]])",
    "const next = new URLSearchParams([...params].toSorted(([a], [b]) => a.localeCompare(b)))",
    "const value = params.get('q')",
    "const present = params.has('q')",
    "for (const [k, v] of params.entries()) console.log(k, v)",
    "const all = params.getAll('q')",
    "const str = params.toString()",
]


@pytest.mark.parametrize("snippet", URL_SEARCH_PARAMS_ALLOWED)
def test_url_search_params_allowed_pattern_passes(run_hook, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/url.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block:\n{stderr}"


HEADERS_BLOCKED: list[tuple[str, str]] = [
    (
        "const headers = new Headers(init)\nheaders.append('X-Trace', id)",
        "web-api.headers.append",
    ),
    (
        "const headers = new Headers(init)\nheaders.set('Authorization', token)",
        "web-api.headers.set",
    ),
    (
        "const headers = new Headers(init)\nheaders.delete('Cookie')",
        "web-api.headers.delete",
    ),
    (
        "function attach(h: Headers): void { h.set('X-Tenant', tenantId) }",
        "web-api.headers.set",
    ),
]


@pytest.mark.parametrize(("snippet", "detector"), HEADERS_BLOCKED)
def test_headers_mutation_blocked(run_hook, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/headers.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"unexpected exit {code}\n{stderr}"
    assert detector in stderr, f"detector {detector} missing in:\n{stderr}"


HEADERS_ALLOWED: list[str] = [
    "const next = new Headers([...headers, ['X-Trace', id]])",
    "const value = headers.get('X-Trace')",
    "const present = headers.has('Authorization')",
    "for (const [k, v] of headers.entries()) console.log(k, v)",
]


@pytest.mark.parametrize("snippet", HEADERS_ALLOWED)
def test_headers_allowed_pattern_passes(run_hook, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/headers.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block:\n{stderr}"


FORM_DATA_BLOCKED: list[tuple[str, str]] = [
    (
        "const form = new FormData()\nform.append('file', file)",
        "web-api.form-data.append",
    ),
    (
        "const form = new FormData()\nform.set('name', 'value')",
        "web-api.form-data.set",
    ),
    (
        "const form = new FormData()\nform.delete('avatar')",
        "web-api.form-data.delete",
    ),
    (
        "function fill(fd: FormData) { fd.append('k', v) }",
        "web-api.form-data.append",
    ),
]


@pytest.mark.parametrize(("snippet", "detector"), FORM_DATA_BLOCKED)
def test_form_data_mutation_blocked(run_hook, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/form.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"unexpected exit {code}\n{stderr}"
    assert detector in stderr, f"detector {detector} missing in:\n{stderr}"


FORM_DATA_ALLOWED: list[str] = [
    (
        "const next = Array.from(form.entries()).reduce("
        "(fd, [k, v]) => { fd.append(k, v); return fd }, new FormData())\n"
        "// @allow-mutation -- reducer initializer is fresh"
    ),
    "const value = form.get('name')",
    "const present = form.has('avatar')",
    "for (const [k, v] of form.entries()) console.log(k, v)",
]


@pytest.mark.parametrize("snippet", FORM_DATA_ALLOWED)
def test_form_data_allowed_pattern_passes(run_hook, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/form.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block:\n{stderr}"


SUPPRESSION_CASES: list[tuple[str, str]] = [
    (
        "const params = new URLSearchParams(q)\n"
        "params.append('q', t) // @allow-mutation -- third-party SDK retains pointer",
        "url-search-params suppression",
    ),
    (
        "const headers = new Headers(init)\n"
        "headers.set('X', v) // @allow-mutation -- middleware mutates in place by contract",
        "headers suppression",
    ),
    (
        "const fd = new FormData()\n"
        "fd.append('file', f) // @allow-mutation -- XHR.send keeps the reference",
        "form-data suppression",
    ),
]


@pytest.mark.parametrize(("snippet", "label"), SUPPRESSION_CASES)
def test_web_api_suppression_marker_bypasses_detector(run_hook, snippet, label):
    # Arrange
    payload = make_edit_payload("/repo/src/web.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: expected pass, got exit {code}\n{stderr}"


def test_dom_corpus_does_not_trigger_web_api_detectors(run_hook):
    # Arrange
    snippet = (
        "const params = new URLSearchParams(window.location.search)\n"
        "const value = params.get('q')\n"
        "const next = new URLSearchParams([...params, ['page', '2']])\n"
    )
    payload = make_edit_payload("/repo/src/dom-aware.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block on read-only URLSearchParams chain:\n{stderr}"


DOM_PROLOGUE: str = """declare const document: any;

function applyDom(): void {
  const root = document.getElementById('app');
  root.innerHTML = '<p>hi</p>';
  root.textContent = 'plain';
  root.className = 'card';
  root.style.color = 'red';
  root.dataset.value = '42';
  root.scrollTop = 0;
  const submitBtn = document.querySelector('button');
  submitBtn.disabled = true;
  const host = document.querySelector('my-element');
  host.shadowRoot.innerHTML = '<slot/>';
}
"""

URL_SEARCH_PARAMS_FIXTURE: str = (
    DOM_PROLOGUE
    + """
function rewriteQuery(query: string, term: string): URLSearchParams {
  const params = new URLSearchParams(query);
  params.append('q', term);
  params.set('page', '1');
  params.delete('legacy');
  params.sort();
  return params;
}
"""
)

HEADERS_FIXTURE: str = (
    DOM_PROLOGUE
    + """
function buildRequestHeaders(init: HeadersInit, token: string): Headers {
  const headers = new Headers(init);
  headers.append('X-Trace-Id', 'trace-123');
  headers.set('Authorization', `Bearer ${token}`);
  headers.delete('Cookie');
  return headers;
}
"""
)

FORM_DATA_FIXTURE: str = (
    DOM_PROLOGUE
    + """
function buildUploadForm(file: Blob, name: string): FormData {
  const form = new FormData();
  form.append('file', file);
  form.set('name', name);
  form.delete('legacy_field');
  return form;
}
"""
)

FORBIDDEN_DOM_FRAGMENTS: list[str] = [
    "innerHTML",
    "textContent",
    "className",
    "dataset.value",
    "scrollTop",
    "shadowRoot",
    "submitBtn.disabled",
]


def _assert_dom_not_flagged(stderr: str) -> None:
    """No DOM line may appear in the detector report.

    DOM mutations are silently allowed; their presence in the diagnostic
    output would indicate a regression in the DOM allowlist.
    """
    for fragment in FORBIDDEN_DOM_FRAGMENTS:
        assert fragment not in stderr, (
            f"DOM line '{fragment}' must not appear in detector report:\n{stderr}"
        )


def test_mixed_url_search_params_fixture(run_hook):
    """Item 209a: URLSearchParams mutations flagged, DOM lines silent."""
    # Arrange
    payload = make_edit_payload("/repo/src/mixed-url.ts", URL_SEARCH_PARAMS_FIXTURE)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"expected block, got exit {code}\n{stderr}"
    for tag in [
        "web-api.url-search-params.append",
        "web-api.url-search-params.set",
        "web-api.url-search-params.delete",
        "web-api.url-search-params.sort",
    ]:
        assert tag in stderr, f"expected hit {tag} missing in:\n{stderr}"
    _assert_dom_not_flagged(stderr)


def test_mixed_headers_fixture(run_hook):
    """Item 209b: Headers mutations flagged, DOM lines silent."""
    # Arrange
    payload = make_edit_payload("/repo/src/mixed-headers.ts", HEADERS_FIXTURE)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"expected block, got exit {code}\n{stderr}"
    for tag in [
        "web-api.headers.append",
        "web-api.headers.set",
        "web-api.headers.delete",
    ]:
        assert tag in stderr, f"expected hit {tag} missing in:\n{stderr}"
    _assert_dom_not_flagged(stderr)


def test_mixed_form_data_fixture(run_hook):
    """Item 209c: FormData mutations flagged, DOM lines silent."""
    # Arrange
    payload = make_edit_payload("/repo/src/mixed-form.ts", FORM_DATA_FIXTURE)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"expected block, got exit {code}\n{stderr}"
    for tag in [
        "web-api.form-data.append",
        "web-api.form-data.set",
        "web-api.form-data.delete",
    ]:
        assert tag in stderr, f"expected hit {tag} missing in:\n{stderr}"
    _assert_dom_not_flagged(stderr)


INDEXED_DB_OUT_OF_SCOPE: list[str] = [
    "const tx = db.transaction('store', 'readwrite')\ntx.objectStore('store').put({id: 1, name: 'x'})",
    "const store = db.transaction('store', 'readwrite').objectStore('store')\nstore.add({id: 2, value: 'y'})",
    "const store = db.transaction('store', 'readwrite').objectStore('store')\nstore.delete(42)",
    "const cursor = store.openCursor()\ncursor.update({id: 3, name: 'updated'})",
    "const cursor = store.openCursor()\ncursor.delete()",
    "const store = db.transaction('store', 'readwrite').objectStore('store')\nstore.clear()",
]


@pytest.mark.parametrize("snippet", INDEXED_DB_OUT_OF_SCOPE)
def test_indexed_db_mutations_out_of_scope(run_hook, snippet):
    """Item 206: IndexedDB cursor and transaction mutations are out of scope.

    The IndexedDB API is inherently mutating; flagging it would generate
    noise. The mutation hook governs JS values, not Web platform side-effect APIs.
    """
    # Arrange
    payload = make_edit_payload("/repo/src/indexed-db.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block on IndexedDB API:\n{stderr}"


WEB_STORAGE_OUT_OF_SCOPE: list[str] = [
    "localStorage.setItem('token', 'abc')",
    "localStorage.removeItem('token')",
    "localStorage.clear()",
    "sessionStorage.setItem('flag', '1')",
    "sessionStorage.removeItem('flag')",
    "sessionStorage.clear()",
    "window.localStorage.setItem('k', 'v')",
    "window.sessionStorage.removeItem('k')",
]


@pytest.mark.parametrize("snippet", WEB_STORAGE_OUT_OF_SCOPE)
def test_web_storage_mutations_out_of_scope(run_hook, snippet):
    """Item 207: Web Storage setItem/removeItem/clear are out of scope.

    Web Storage is a side-effect API. The 'no module-level side effects'
    rule governs its placement; the mutation hook does not flag it.
    """
    # Arrange
    payload = make_edit_payload("/repo/src/storage.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block on Web Storage API:\n{stderr}"
