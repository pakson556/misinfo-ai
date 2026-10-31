"""Live monitor: reading stream messages, hiding identities, and flagging. No network needed."""

import json

import pytest
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
    reply = json.loads(_v1(LONG))
    reply["commit"]["record"]["reply"] = {"parent": {}}
    assert extract_post(json.dumps(reply)) is None  # replies skipped
    pic = json.loads(_v1(LONG))
    pic["commit"]["record"]["embed"] = {"$type": "app.bsky.embed.images"}
    assert extract_post(json.dumps(pic)) is None  # short text + picture skipped


def test_anonymise_removes_people_and_links():
    out = anonymise("Ask @jane.bsky.social about it https://example.com/x and www.site.com/path now")
    assert "jane" not in out and "example.com" not in out and "site.com" not in out
    assert "@someone" in out and "[link]" in out


def test_monitor_flags_warning_signs_but_not_plain_posts():
    m = Monitor()
    assert m.process(LONG) is True
    assert m.process("The council meeting on Tuesday approved the new budget for road repairs across the county.") is False
    assert m.process("HARD-FOUGHT GOAL!!! WHAT A FINISH from the striker in the 29th minute, the crowd is going wild") is False
    assert (
        m.process(
            "Interestingly enough, all of their drawings ended up looking very similar. They were always amazed by this! Please share!"
        )
        is False
    )
    snap = m.snapshot()
    assert snap["seen"] == 4 and snap["flagged"] == 1
    assert snap["recent"][0]["tactics"] and "did:" not in json.dumps(snap)
    assert snap["top_tactics"][0]["count"] >= 1


@pytest.mark.asyncio
async def test_lookup_attaches_close_factcheck_only(monkeypatch):
    from app import monitor as mon
    from app.schemas import Evidence

    async def fake_factcheck(text):
        return [
            Evidence(
                title="Fact-check",
                url="https://fullfact.org/x",
                domain="fullfact.org",
                snippet="Doctors don't want you to know this simple trick that cures cancer",
                kind="factcheck",
                publisher="Full Fact",
                rating="False",
            ),
            Evidence(
                title="Other",
                url="https://x.org/y",
                domain="x.org",
                snippet="The moon is made of cheese",
                kind="factcheck",
                rating="False",
            ),
        ]

    monkeypatch.setattr(mon, "google_factcheck", fake_factcheck)
    m = Monitor()
    item = {"text": LONG, "factcheck": None}
    await m.lookup(item)
    assert item["factcheck"]["publisher"] == "Full Fact" and item["factcheck"]["verdict"] == "REFUTED"
    assert m.snapshot()["matched_claims"][0]["count"] == 1

    other = {"text": "The council approved the new budget for road repairs across the whole county this week.", "factcheck": None}
    await m.lookup(other)
    assert other["factcheck"] is None and m.matched == 1


def test_parse_gdelt_tidies_and_dedupes():
    from app.monitor import parse_gdelt

    data = {
        "articles": [
            {
                "url": "https://a.com/1",
                "title": "Viral hoax debunked",
                "seendate": "20261031T150000Z",
                "domain": "a.com",
                "sourcecountry": "Ghana",
            },
            {"url": "https://a.com/1", "title": "duplicate", "seendate": "20261031T150000Z"},
            {
                "url": "https://b.com/2",
                "title": "Fact check: no, the photo is fake",
                "seendate": "20261031T153000Z",
                "domain": "b.com",
                "sourcecountry": "United Kingdom",
            },
            {"url": "", "title": "no url"},
        ]
    }
    out = parse_gdelt(data)
    assert [a["url"] for a in out] == ["https://b.com/2", "https://a.com/1"]  # newest first, no duplicate
    assert out[1]["country"] == "Ghana" and out[0]["time"].startswith("2026-10-31T15:30")
    assert parse_gdelt({}) == []
