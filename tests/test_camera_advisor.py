"""tests/test_camera_advisor.py — Camera advisor tests."""

import pytest

from modules.camera_advisor import CameraAdvisor, CAMERA_OPTIONS


@pytest.fixture
def advisor():
    return CameraAdvisor()


class TestCameraOptions:
    def test_has_options(self):
        assert len(CAMERA_OPTIONS) >= 8

    def test_all_have_required_fields(self):
        for cam in CAMERA_OPTIONS:
            assert "name" in cam
            assert "type" in cam
            assert "price_usd" in cam
            assert "pros" in cam
            assert "cons" in cam
            assert "best_for" in cam

    def test_types_present(self):
        types = {c["type"] for c in CAMERA_OPTIONS}
        assert "picamera" in types
        assert "usb" in types


class TestRecommend:
    def test_recommend_by_budget(self, advisor):
        results = advisor.recommend(budget=40)
        for r in results:
            assert r["price_usd"] <= 40

    def test_recommend_with_night_vision(self, advisor):
        results = advisor.recommend(night_vision=True)
        for r in results:
            assert r["night_vision"] is True
        assert len(results) > 0

    def test_recommend_with_auto_focus(self, advisor):
        results = advisor.recommend(auto_focus_required=True)
        for r in results:
            assert r["auto_focus"] is True

    def test_recommend_by_pi_model(self, advisor):
        results = advisor.recommend(pi_model="Pi 4")
        for r in results:
            assert "Pi 4" in r["pi_compatibility"]

    def test_recommend_by_type(self, advisor):
        results = advisor.recommend(camera_type="usb")
        for r in results:
            assert r["type"] == "usb"

    def test_recommend_returns_reason(self, advisor):
        results = advisor.recommend(budget=50)
        for r in results:
            assert "recommendation_reason" in r

    def test_recommend_no_matches(self, advisor):
        results = advisor.recommend(budget=1)
        assert results == []

    def test_recommend_sorted_by_price(self, advisor):
        results = advisor.recommend()
        prices = [r["price_usd"] for r in results]
        assert prices == sorted(prices)


class TestGetCamera:
    def test_get_by_name(self, advisor):
        cam = advisor.get_camera("Pi Camera Module 3")
        assert cam is not None
        assert "11.9 MP" in cam["resolution"]

    def test_get_by_partial_name(self, advisor):
        cam = advisor.get_camera("C920")
        assert cam is not None
        assert "Logitech" in cam["name"]

    def test_get_not_found(self, advisor):
        assert advisor.get_camera("Nonexistent Camera") is None


class TestCompare:
    def test_compare_two_cameras(self, advisor):
        result = advisor.compare("Pi Camera Module 3", "C920")
        assert "camera_1" in result
        assert "camera_2" in result
        assert "price_difference" in result
        assert "winner" in result

    def test_compare_not_found(self, advisor):
        result = advisor.compare("Nonexistent", "Also Nonexistent")
        assert "error" in result


class TestSummary:
    def test_summary_structure(self, advisor):
        summary = advisor.get_summary()
        assert "total_options" in summary
        assert "price_range" in summary
        assert "types" in summary
        assert "night_vision_options" in summary

    def test_summary_has_night_vision(self, advisor):
        summary = advisor.get_summary()
        assert len(summary["night_vision_options"]) > 0


class TestListAll:
    def test_list_all(self, advisor):
        all_cams = advisor.list_all()
        assert len(all_cams) == len(CAMERA_OPTIONS)

    def test_get_by_type(self, advisor):
        usb_cams = advisor.get_by_type("usb")
        for c in usb_cams:
            assert c["type"] == "usb"