import os
import types
import importlib
import pytest
import re

# -------- Config: where to import your app from ----------
APP_MODULE_NAME = os.getenv("APP_MODULE", "index") 

# ------------- Import the target app module ----------------
app_module = importlib.import_module(APP_MODULE_NAME)

# ------------- Pytest fixtures ------------------------------
@pytest.fixture(scope="session")
def app():
    app_module.app.config.update(TESTING=True)
    return app_module.app

@pytest.fixture(scope="session")
def client(app):
    return app.test_client()

@pytest.fixture(scope="session")
def helpers():
    return {
        "text_to_number": app_module.text_to_number,
        "number_to_text": app_module.number_to_text,
        "base64_to_number": app_module.base64_to_number,
        "number_to_base64": app_module.number_to_base64,
    }

# ----------------- Helper for API calls ---------------------
def post_convert(client, input_value, input_type, output_type):
    return client.post(
        "/convert",
        json={"input": input_value, "inputType": input_type, "outputType": output_type},
    )

def assert_ok_json(rsp):
    assert rsp.is_json
    data = rsp.get_json()
    assert "result" in data and "error" in data
    return data

# ============================================================
# 1) Tests on converting all input types into all other input types
#    (happy-path conversions + canonical/normalized outputs)
# ============================================================

# --- TEXT input -> others (limited vocabulary per implementation) ---

@pytest.mark.parametrize("text, dec, bin_, oct_, hex_, b64, txt", [
    ("zero",  "0",   "0",    "0",   "0",   "AA==", "zero"),
    ("one",   "1",   "1",    "1",   "1",   "AQ==", "one"),
    ("five",  "5",   "101",  "5",   "5",   "BQ==", "five"),
    ("ten",   "10",  "1010", "12",  "a",   "Cg==", "ten"),
    ("nil",   "0",   "0",    "0",   "0",   "AA==", "zero"),
    (" FivE! ", "5", "101",  "5",   "5",   "BQ==", "five"),
])
def test_text_input_full_matrix(client, text, dec, bin_, oct_, hex_, b64, txt):
    # text -> decimal
    d = assert_ok_json(post_convert(client, text, "text", "decimal"));      assert d["error"] is None and d["result"] == dec
    # text -> binary
    b = assert_ok_json(post_convert(client, text, "text", "binary"));       assert b["error"] is None and b["result"] == bin_
    # text -> octal
    o = assert_ok_json(post_convert(client, text, "text", "octal"));        assert o["error"] is None and o["result"] == oct_
    # text -> hexadecimal
    h = assert_ok_json(post_convert(client, text, "text", "hexadecimal"));  assert h["error"] is None and h["result"] == hex_
    # text -> base64   (NOTE: current code returns "" for zero; that will FAIL for "zero"/"nil")
    bs = assert_ok_json(post_convert(client, text, "text", "base64"));      assert bs["error"] is None and bs["result"] == b64
    # text -> text (normalization)
    t = assert_ok_json(post_convert(client, text, "text", "text"));         assert t["error"] is None and t["result"] == txt


# --- DECIMAL input -> others (canonical outputs, trimming leading zeros) ---

@pytest.mark.parametrize("dec, bin_, oct_, hex_, b64, txt", [
    ("0",    "0",    "0",   "0",   "AA==", "zero"),
    ("1",    "1",    "1",   "1",   "AQ==", "one"),
    ("5",    "101",  "5",   "5",   "BQ==", "five"),
    ("10",   "1010", "12",  "a",   "Cg==", "ten"),
    ("255",  "11111111", "377", "ff", "/w==", None),  # txt=None => skip text assertion for >10
    ("0005", "101",  "5",   "5",   "BQ==", "five"),   # leading zeros normalize
])
def test_decimal_input_full_matrix(client, dec, bin_, oct_, hex_, b64, txt):
    b = assert_ok_json(post_convert(client, dec, "decimal", "binary"));       assert b["error"] is None and b["result"] == bin_
    o = assert_ok_json(post_convert(client, dec, "decimal", "octal"));        assert o["error"] is None and o["result"] == oct_
    h = assert_ok_json(post_convert(client, dec, "decimal", "hexadecimal"));  assert h["error"] is None and h["result"] == hex_
    bs = assert_ok_json(post_convert(client, dec, "decimal", "base64"));      assert bs["error"] is None and bs["result"] == b64
    # decimal -> decimal identity normalization
    di = assert_ok_json(post_convert(client, dec, "decimal", "decimal"));     assert di["error"] is None and di["result"] == str(int(dec))
    # decimal -> text (only assert exact for <=10)
    if txt is not None:
        t = assert_ok_json(post_convert(client, dec, "decimal", "text"));     assert t["error"] is None and t["result"] == txt


# --- BINARY input -> others (accept whitespace; canonicalize, no leading zeros) ---

@pytest.mark.parametrize("bin_in, dec, oct_, hex_, b64, bin_out", [
    ("0",          "0",   "0",   "0",   "AA==", "0"),
    ("1",          "1",   "1",   "1",   "AQ==", "1"),
    ("101",        "5",   "5",   "5",   "BQ==", "101"),
    ("1010",       "10",  "12",  "a",   "Cg==", "1010"),
    ("11111111",   "255", "377", "ff",  "/w==", "11111111"),
    ("   00101  ", "5",   "5",   "5",   "BQ==", "101"),  # whitespace + leading zeros
])
def test_binary_input_full_matrix(client, bin_in, dec, oct_, hex_, b64, bin_out):
    d = assert_ok_json(post_convert(client, bin_in, "binary", "decimal"));      assert d["error"] is None and d["result"] == dec
    o = assert_ok_json(post_convert(client, bin_in, "binary", "octal"));        assert o["error"] is None and o["result"] == oct_
    h = assert_ok_json(post_convert(client, bin_in, "binary", "hexadecimal"));  assert h["error"] is None and h["result"] == hex_
    bs = assert_ok_json(post_convert(client, bin_in, "binary", "base64"));      assert bs["error"] is None and bs["result"] == b64
    # binary -> binary normalization
    bb = assert_ok_json(post_convert(client, bin_in, "binary", "binary"));      assert bb["error"] is None and bb["result"] == bin_out
    # small numbers -> text exact
    if dec in {"0","1","5","10"}:
        expected_text = {"0":"zero","1":"one","5":"five","10":"ten"}[dec]
        t = assert_ok_json(post_convert(client, bin_in, "binary", "text"));     assert t["error"] is None and t["result"] == expected_text


# --- OCTAL input -> others ---

@pytest.mark.parametrize("oct_in, dec, bin_, hex_, b64, oct_out", [
    ("0",     "0",   "0",       "0",   "AA==", "0"),
    ("1",     "1",   "1",       "1",   "AQ==", "1"),
    ("5",     "5",   "101",     "5",   "BQ==", "5"),
    ("12",    "10",  "1010",    "a",   "Cg==", "12"),
    ("377",   "255", "11111111","ff",  "/w==", "377"),
    ("00012", "10",  "1010",    "a",   "Cg==", "12"),  # leading zeros normalized
])
def test_octal_input_full_matrix(client, oct_in, dec, bin_, hex_, b64, oct_out):
    d = assert_ok_json(post_convert(client, oct_in, "octal", "decimal"));       assert d["error"] is None and d["result"] == dec
    b = assert_ok_json(post_convert(client, oct_in, "octal", "binary"));        assert b["error"] is None and b["result"] == bin_
    h = assert_ok_json(post_convert(client, oct_in, "octal", "hexadecimal"));   assert h["error"] is None and h["result"] == hex_
    bs = assert_ok_json(post_convert(client, oct_in, "octal", "base64"));       assert bs["error"] is None and bs["result"] == b64
    oo = assert_ok_json(post_convert(client, oct_in, "octal", "octal"));        assert oo["error"] is None and oo["result"] == oct_out
    if dec in {"0","1","5","10"}:
        expected_text = {"0":"zero","1":"one","5":"five","10":"ten"}[dec]
        t = assert_ok_json(post_convert(client, oct_in, "octal", "text"));      assert t["error"] is None and t["result"] == expected_text


# --- HEX input -> others (case-insensitive; canonical lowercase output) ---

@pytest.mark.parametrize("hex_in, dec, bin_, oct_, b64, hex_out", [
    ("0",   "0",   "0",        "0",   "AA==", "0"),
    ("1",   "1",   "1",        "1",   "AQ==", "1"),
    ("5",   "5",   "101",      "5",   "BQ==", "5"),
    ("a",   "10",  "1010",     "12",  "Cg==", "a"),
    ("A",   "10",  "1010",     "12",  "Cg==", "a"),   # uppercase input normalized to lowercase output
    ("ff",  "255", "11111111", "377", "/w==", "ff"),
    ("00a", "10",  "1010",     "12",  "Cg==", "a"),   # leading zeros
])
def test_hex_input_full_matrix(client, hex_in, dec, bin_, oct_, b64, hex_out):
    d = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "decimal"));     assert d["error"] is None and d["result"] == dec
    b = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "binary"));      assert b["error"] is None and b["result"] == bin_
    o = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "octal"));       assert o["error"] is None and o["result"] == oct_
    bs = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "base64"));     assert bs["error"] is None and bs["result"] == b64
    hh = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "hexadecimal"));assert hh["error"] is None and hh["result"] == hex_out
    if dec in {"0","1","5","10"}:
        expected_text = {"0":"zero","1":"one","5":"five","10":"ten"}[dec]
        t = assert_ok_json(post_convert(client, hex_in, "hexadecimal", "text"));    assert t["error"] is None and t["result"] == expected_text


# --- BASE64 input -> others (positive values; canonicalization for positive ints) ---

@pytest.mark.parametrize("b64_in, dec, bin_, oct_, hex_, b64_out", [
    ("AQ==", "1",   "1",        "1",   "1",   "AQ=="),
    ("BQ==", "5",   "101",      "5",   "5",   "BQ=="),
    ("Cg==", "10",  "1010",     "12",  "a",   "Cg=="),
    ("/w==", "255", "11111111", "377", "ff",  "/w=="),
])
def test_base64_input_full_matrix(client, b64_in, dec, bin_, oct_, hex_, b64_out):
    d = assert_ok_json(post_convert(client, b64_in, "base64", "decimal"));       assert d["error"] is None and d["result"] == dec
    b = assert_ok_json(post_convert(client, b64_in, "base64", "binary"));        assert b["error"] is None and b["result"] == bin_
    o = assert_ok_json(post_convert(client, b64_in, "base64", "octal"));         assert o["error"] is None and o["result"] == oct_
    h = assert_ok_json(post_convert(client, b64_in, "base64", "hexadecimal"));   assert h["error"] is None and h["result"] == hex_
    bb = assert_ok_json(post_convert(client, b64_in, "base64", "base64"));       assert bb["error"] is None and bb["result"] == b64_out
    if dec in {"0","1","5","10"}:
        expected_text = {"0":"zero","1":"one","5":"five","10":"ten"}[dec]
        t = assert_ok_json(post_convert(client, b64_in, "base64", "text"));      assert t["error"] is None and t["result"] == expected_text

def _norm_words(s: str) -> str:
    # lowercase and collapse spaces/hyphens so "forty two" == "forty-two"
    return re.sub(r"[\s\-]+", " ", s.strip().lower())

@pytest.mark.parametrize("dec, bin_, oct_, hex_, b64, text_variants", [
    ("11", "1011",   "13", "b",  "Cw==", {"eleven"}),
    ("42", "101010", "52", "2a", "Kg==", {"forty two", "forty-two"}),
])
def test_decimal_double_digit_full_matrix(client, dec, bin_, oct_, hex_, b64, text_variants):
    # dec -> bin/oct/hex/base64 (existing assertions)
    b = assert_ok_json(post_convert(client, dec, "decimal", "binary"));      assert b["error"] is None and b["result"] == bin_
    o = assert_ok_json(post_convert(client, dec, "decimal", "octal"));       assert o["error"] is None and o["result"] == oct_
    h = assert_ok_json(post_convert(client, dec, "decimal", "hexadecimal")); assert h["error"] is None and h["result"] == hex_
    s = assert_ok_json(post_convert(client, dec, "decimal", "base64"));      assert s["error"] is None and s["result"] == b64
    d = assert_ok_json(post_convert(client, dec, "decimal", "decimal"));     assert d["error"] is None and d["result"] == str(int(dec))
    # NEW: dec -> text (accept common variants)
    t = assert_ok_json(post_convert(client, dec, "decimal", "text"));        assert t["error"] is None
    assert _norm_words(t["result"]) in {_norm_words(v) for v in text_variants}

# --- NEW: non-decimal double-digit inputs -> TEXT (only 11 and 42) ---
@pytest.mark.parametrize("val, itype, text_variants", [
    ("1011",   "binary",      {"eleven"}),
    ("13",     "octal",       {"eleven"}),
    ("b",      "hexadecimal", {"eleven"}),
    ("Cw==",   "base64",      {"eleven"}),
    ("101010", "binary",      {"forty two", "forty-two"}),
    ("52",     "octal",       {"forty two", "forty-two"}),
    ("2a",     "hexadecimal", {"forty two", "forty-two"}),
    ("Kg==",   "base64",      {"forty two", "forty-two"}),
])
def test_double_digit_non_decimal_inputs_to_text(client, val, itype, text_variants):
    out = assert_ok_json(post_convert(client, val, itype, "text"))
    assert out["error"] is None
    assert _norm_words(out["result"]) in {_norm_words(v) for v in text_variants}

@pytest.mark.parametrize("text, dec, bin_, oct_, hex_, b64", [
    ("eleven",     "11", "1011",   "13", "b",  "Cw=="),
    ("forty-two",  "42", "101010", "52", "2a", "Kg=="),
])
def test_text_double_digit_to_full_matrix(client, text, dec, bin_, oct_, hex_, b64):
    d = assert_ok_json(post_convert(client, text, "text", "decimal"));     assert d["error"] is None and d["result"] == dec
    b = assert_ok_json(post_convert(client, text, "text", "binary"));      assert b["error"] is None and b["result"] == bin_
    o = assert_ok_json(post_convert(client, text, "text", "octal"));       assert o["error"] is None and o["result"] == oct_
    h = assert_ok_json(post_convert(client, text, "text", "hexadecimal")); assert h["error"] is None and h["result"] == hex_
    s = assert_ok_json(post_convert(client, text, "text", "base64"));      assert s["error"] is None and s["result"] == b64
    t = assert_ok_json(post_convert(client, text, "text", "text"));        assert t["error"] is None and t["result"].strip()


# =================================
# 2) Tests on edge case errors
#    (invalid digits, negative handling, base64 quirks, prefixes)
# =================================

# Invalid text outside supported scope
@pytest.mark.parametrize("text", [
  "abc", "", " "
])
def test_text_to_number_invalid_raises(helpers, text):
    with pytest.raises(ValueError):
        helpers["text_to_number"](text)

# Invalid digits per base
@pytest.mark.parametrize("bad_binary", ["2", "102", "10a01", "", " ", "0b1010"])
def test_invalid_binary_rejected(client, bad_binary):
    data = assert_ok_json(post_convert(client, bad_binary, "binary", "decimal"))
    assert data["result"] is None and data["error"]

@pytest.mark.parametrize("bad_octal", ["8", "9", "77a", " ", "0o12"])
def test_invalid_octal_rejected(client, bad_octal):
    data = assert_ok_json(post_convert(client, bad_octal, "octal", "decimal"))
    assert data["result"] is None and data["error"]

@pytest.mark.parametrize("bad_hex", ["xz", "g", "1x", " ", "0xFF"])
def test_invalid_hex_rejected(client, bad_hex):
    data = assert_ok_json(post_convert(client, bad_hex, "hexadecimal", "decimal"))
    assert data["result"] is None and data["error"]

# Negative number handling (sign preservation for outputs)
def test_negative_decimal_to_binary_preserve_sign(client):
    data = assert_ok_json(post_convert(client, "-5", "decimal", "binary"))
    assert data["error"] is None and data["result"] == "-101"   # current code likely FAILS

def test_negative_decimal_to_octal_preserve_sign(client):
    data = assert_ok_json(post_convert(client, "-255", "decimal", "octal"))
    assert data["error"] is None and data["result"] == "-377"   # likely FAIL

def test_negative_decimal_to_hex_preserve_sign(client):
    data = assert_ok_json(post_convert(client, "-31", "decimal", "hexadecimal"))
    assert data["error"] is None and data["result"] == "-1f"    # likely FAIL

# Negative inputs in non-decimal bases (int() accepts "-<digits>" with base)
@pytest.mark.parametrize("inp, itype, expected", [
    ("-101", "binary", "-5"),
    ("-377", "octal", "-255"),
    ("-ff",  "hexadecimal", "-255"),
])
def test_negative_inputs_in_bases_to_decimal(client, inp, itype, expected):
    data = assert_ok_json(post_convert(client, inp, itype, "decimal"))
    assert data["error"] is None and data["result"] == expected

# Base64 invalid strings should be rejected (decoder should validate)
@pytest.mark.parametrize("bad_b64", ["not_base64", "abc?d", "A", "===", "!!!!", "YWJj*"])
def test_invalid_base64_rejected(client, bad_b64):
    data = assert_ok_json(post_convert(client, bad_b64, "base64", "decimal"))
    assert data["result"] is None and data["error"]

# Base64 canonicalization quirks
def test_base64_zero_should_not_be_empty_api(client):
    # Current code encodes 0 to empty string; canonical should be "AA=="
    d0 = assert_ok_json(post_convert(client, "0", "decimal", "base64"))
    assert d0["error"] is None and d0["result"] == "AA=="  # likely FAIL

def test_base64_leading_zero_canonicalization_api(client):
    # "AAE=" -> bytes 00 01 -> int(1) -> re-encode canonical "AQ=="
    data = assert_ok_json(post_convert(client, "AAE=", "base64", "base64"))
    assert data["error"] is None and data["result"] == "AQ=="

# Optional: accept data URLs for base64 inputs (nice-to-have)
def test_base64_data_url_accepted_api(client):
    data = assert_ok_json(post_convert(client, "data:text/plain;base64,AQ==", "base64", "decimal"))
    assert data["error"] is None and data["result"] == "1"


# ===========================
# 3) Tests on the API itself
#    (routes, payload validation, contract)
# ===========================

def test_index_route_renders_html(app, client):
    rsp = client.get("/")
    assert rsp.status_code == 200
    assert b"<" in rsp.data

def test_convert_success_json_contract(client):
    rsp = post_convert(client, "10", "decimal", "decimal")
    assert rsp.status_code == 200
    assert rsp.is_json
    data = rsp.get_json()
    assert set(data.keys()) == {"result", "error"}
    assert data["error"] is None and data["result"] == "10"

def test_missing_json_body(client):
    rsp = client.post("/convert", data="not json", content_type="application/json")
    assert rsp.status_code == 200  # current implementation returns 200 with error payload
    data = rsp.get_json()
    assert "error" in data and data["error"]

def test_missing_required_fields(client):
    rsp = client.post("/convert", json={"input": "10"})  # no inputType/outputType
    assert rsp.status_code == 200
    data = rsp.get_json()
    assert data["result"] is None and data["error"]

def test_invalid_input_output_type_names(client):
    d1 = assert_ok_json(post_convert(client, "10", "DECIMAL", "binary"))  # wrong casing
    assert d1["result"] is None and d1["error"]
    d2 = assert_ok_json(post_convert(client, "10", "decimal", "BINARY"))
    assert d2["result"] is None and d2["error"]

def test_wrong_content_type_form_encoded(client):
    rsp = client.post("/convert", data={"input": "10", "inputType": "decimal", "outputType": "binary"})
    assert rsp.status_code == 200
    assert rsp.is_json
    data = rsp.get_json()
    assert data["result"] is None and data["error"]

def test_convert_method_not_allowed(client):
    rsp = client.get("/convert")
    assert rsp.status_code in (405, 200)  # some dev servers may 200 with error JSON
    if rsp.is_json:
        data = rsp.get_json()
        assert "error" in data