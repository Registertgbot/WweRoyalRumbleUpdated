from services import hub
from services.hub import HubStatus


def test_find_welcome_prefers_assets_root_and_accepts_images_and_mp4(tmp_path):
    gifs = tmp_path / "gifs"
    gifs.mkdir()
    assert hub.find_welcome(gifs) is None
    (gifs / "welcome.mp4").write_bytes(b"x")
    assert hub.find_welcome(gifs).name == "welcome.mp4"
    (tmp_path / "welcome.jpg").write_bytes(b"x")
    assert hub.find_welcome(gifs).name == "welcome.jpg"        # assets/welcome.jpg wins


def test_captions_fit_telegram_limit_and_show_running_modes():
    plain = hub.welcome_caption()
    busy = hub.welcome_caption(HubStatus(rumble=True, tag=True, mitb=True))
    assert len(plain) <= hub.CAPTION_LIMIT and len(busy) <= hub.CAPTION_LIMIT
    assert "running" not in plain.lower() and busy.lower().count("ʀᴜɴɴɪɴɢ") == 3
