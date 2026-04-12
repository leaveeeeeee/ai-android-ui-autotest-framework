import pytest


@pytest.mark.smoke
@pytest.mark.device
def test_demo_login_button_exists(demo_page):
    assert demo_page.is_visible(demo_page.login_button)
