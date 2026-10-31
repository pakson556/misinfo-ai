"""Live monitor: reading stream messages, hiding identities, and flagging. No network needed."""

import json

from app.monitor import Monitor, anonymise, extract_post

LONG = "BREAKING!!! Doctors don't want you to know this simple trick that cures cancer. Share this before they delete it!"


def _v1(text, langs=("en",), op="create"):
    return json.dumps(
        {
            "did": "did:plc:abc",
            "time_us": 1,
            "kind": "commit",
            "commit": {"operation": op, "collection": "app.bsky.feed.post", "record": {"text": text, "langs": list(langs)}},
        }
    )


def _v2(text):
    return json.dumps(
        {"payload": {"operation": "create", "collection": "app.bsky.feed.post", "record": {"text": text, "langs": ["en"]}}}
    )


def test_extract_post_handles_both_formats_and_filters():
    assert extract_post(_v1(LONG)) == LONG
    assert extract_post(_v2(LONG)) == LONG
    assert extract_post(_v1(LONG, langs=("pt",))) is None  # not English
    assert extract_post(_v1(LONG, op="delete")) is None  # not a new post
    assert extract_post(_v1("too short")) is None
    assert extract_post("not json") is None


def test_anonymise_removes_people_and_links():
    out = anonymise("Ask @jane.bsky.social about it https://example.com/x and www.site.com/path now")
    assert "jane" not in out and "example.com" not in out and "site.com" not in out
    assert "@someone" in out and "[link]" in out


def test_monitor_flags_warning_signs_but_not_plain_posts():
    m = Monitor()
    assert m.process(LONG) is True
    assert m.process("The council meeting on Tuesday approved the new budget for road repairs across the county.") is False
    assert m.process("HARD-FOUGHT GOAL!!! WHAT A FINISH from the striker in the 29th minute, the crowd is going wild") is False
    snap = m.snapshot()
    assert snap["seen"] == 3 and snap["flagged"] == 1
    assert snap["recent"][0]["tactics"] and "did:" not in json.dumps(snap)
    assert snap["top_tactics"][0]["count"] >= 1
