import json

import pytest

from dubber import sites

FUTURE, PAST = 4_000_000_000, 1_000_000_000


def line(domain, name, expires=FUTURE, value="v"):
    return f"{domain}\tTRUE\t/\tTRUE\t{expires}\t{name}\t{value}"


def test_site_for_url():
    assert sites.site_for_url("https://www.tiktok.com/@a/video/7345").key == "tiktok"
    assert sites.site_for_url("https://vm.tiktok.com/ZMabc/").key == "tiktok"
    assert sites.site_for_url("https://www.instagram.com/reel/C1x_y-Z/").key == "instagram"
    assert sites.site_for_url("https://fb.watch/abc/").key == "facebook"
    assert sites.site_for_url("https://m.facebook.com/watch/?v=1").key == "facebook"
    assert sites.site_for_url("https://youtu.be/x").key == "youtube"
    assert sites.site_for_url("https://notfacebook.com/x") is None
    assert sites.site_for_url("https://vimeo.com/1") is None


def test_video_id_is_folder_safe_and_keeps_youtube_ids():
    assert sites.video_id("Youtube", "qD0_yWgifDM") == "qD0_yWgifDM"  # old caches keep their folder
    assert sites.video_id("TikTok", "7345123456789") == "tiktok-7345123456789"
    assert sites.video_id("Instagram", "C1x_y-Z") == "instagram-C1x_y-Z"
    odd = sites.video_id("Facebook", "1234:5678/видео")
    assert odd.startswith("facebook-") and len(odd) == len("facebook-") + 16
    assert sites.video_id("Facebook", "1234:5678/видео") == odd  # stable: same video, same folder


def test_parse_keeps_only_supported_sites_and_httponly_lines():
    text = "\n".join(["# Netscape HTTP Cookie File", line(".instagram.com", "sessionid"),
                      "#HttpOnly_" + line(".facebook.com", "c_user"), line(".bank.com", "secret"),
                      line(".google.com", "SID"), "garbage line", ""])
    cookies = sites.parse(text)
    assert [(c.domain, c.name) for c in cookies] == [(".instagram.com", "sessionid"), (".facebook.com", "c_user")]
    assert cookies[1].line.startswith("#HttpOnly_")  # kept as written: yt-dlp reads the marker


def test_parse_json_export():
    data = [{"domain": ".tiktok.com", "name": "sessionid", "value": "abc", "path": "/", "secure": True,
             "httpOnly": True, "expirationDate": FUTURE + 0.5},
            {"domain": "www.example.com", "name": "x", "value": "1"}]
    cookies = sites.parse(json.dumps(data))
    assert [(c.domain, c.name, c.expires) for c in cookies] == [(".tiktok.com", "sessionid", FUTURE)]


def test_merge_replaces_a_site_and_keeps_the_others():
    saved = sites.merge("", "\n".join([line(".instagram.com", "sessionid", value="old"),
                                       line(".facebook.com", "c_user")]))
    assert saved.startswith("# Netscape HTTP Cookie File")
    again = sites.merge(saved, line(".instagram.com", "sessionid", value="new"))
    assert "\tnew" in again and "\told" not in again and "c_user" in again
    with pytest.raises(sites.CookieError):
        sites.merge(saved, line(".bank.com", "secret"))
    with pytest.raises(sites.CookieError):
        sites.merge(saved, "not a cookies file")


def test_summary_per_site():
    text = "\n".join([line(".instagram.com", "sessionid"), line(".instagram.com", "csrftoken"),
                      line(".facebook.com", "c_user", expires=PAST), line(".tiktok.com", "sessionid", expires=0)])
    by_site = {s["site"]: s for s in sites.summary(text, now=2_000_000_000)}
    assert by_site["instagram"]["logged_in"] and by_site["instagram"]["expires"] == FUTURE
    assert not by_site["facebook"]["logged_in"]  # expired login
    assert by_site["tiktok"]["logged_in"] and by_site["tiktok"]["expires"] == 0  # until the browser closes
    assert not by_site["youtube"]["logged_in"]
