"""ROI 预测模块 — 冒烟测试（无需 DB）。"""
from App.services.roi_forecaster import RoiForecaster, forecast_roi
import inspect


def test_instantiation():
    f = RoiForecaster()
    assert f.confidence_level == 0.80
    print("Test 1 - RoiForecaster() OK")


def test_custom_confidence():
    f2 = RoiForecaster(confidence_level=0.90)
    assert f2.confidence_level == 0.90
    print("Test 2 - confidence_level=0.90 OK")


def test_invalid_confidence():
    try:
        RoiForecaster(confidence_level=1.5)
        assert False, "should have raised ValueError"
    except ValueError:
        print("Test 3 - Invalid confidence level raises ValueError OK")


def test_linear_regression():
    f = RoiForecaster()
    reg = f._linear_regression([0, 1, 2, 3, 4], [1.0, 1.2, 1.1, 1.3, 1.4])
    print("Test 4 - linear_regression: slope={:.4f}, r2={:.4f} OK".format(reg["slope"], reg["r_squared"]))
    assert reg["slope"] > 0
    assert 0 < reg["r_squared"] < 1


def test_slope_direction():
    f = RoiForecaster()
    reg_up = f._linear_regression([0, 1, 2], [1.0, 1.5, 2.0])
    print("Test 5 - upward slope={:.4f} OK".format(reg_up["slope"]))
    assert reg_up["slope"] > 0

    reg_down = f._linear_regression([0, 1, 2], [2.0, 1.5, 1.0])
    print("Test 6 - downward slope={:.4f} OK".format(reg_down["slope"]))
    assert reg_down["slope"] < 0


def test_t_stat():
    f = RoiForecaster()
    t5 = f._compute_t_stat(5)
    t30 = f._compute_t_stat(30)
    t100 = f._compute_t_stat(100)
    print("Test 7 - t_stat(5)={:.3f}, t_stat(30)={:.3f}, t_stat(100)={:.3f} OK".format(t5, t30, t100))
    assert 1.4 < t5 < 1.5
    assert 1.3 < t30 < 1.32
    assert t100 < 1.29


def test_empty_result():
    f = RoiForecaster()
    empty = f._empty_result("TEST-SKU", "no data")
    assert empty["sku_id"] == "TEST-SKU"
    assert empty["warning"] == "no data"
    assert empty["forecast"] == []
    assert empty["historical"] == []
    print("Test 8 - _empty_result OK")


def test_forecast_exists():
    assert inspect.iscoroutinefunction(forecast_roi)
    print("Test 9 - forecast_roi is async function OK")


if __name__ == "__main__":
    test_instantiation()
    test_custom_confidence()
    test_invalid_confidence()
    test_linear_regression()
    test_slope_direction()
    test_t_stat()
    test_empty_result()
    test_forecast_exists()
    print("\nAll tests passed!")
