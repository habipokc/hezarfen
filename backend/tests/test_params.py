import pytest

from hezarfen.api.errors import ApiError
from hezarfen.api.params import parse_bbox, parse_bool, parse_csv_choices, parse_int, parse_unix


def test_bbox_parses_lon_lat_order():
    assert parse_bbox("27.5,40.4,30.2,41.6") == (27.5, 40.4, 30.2, 41.6)
    assert parse_bbox(" 27.5 , 40.4 ,30.2, 41.6 ") == (27.5, 40.4, 30.2, 41.6)


@pytest.mark.parametrize(
    "raw",
    [
        "27.5,40.4,30.2",  # three numbers
        "27.5,40.4,30.2,41.6,1",  # five
        "a,40.4,30.2,41.6",
        "nan,40.4,30.2,41.6",
        "inf,40.4,30.2,41.6",
        "30.2,40.4,27.5,41.6",  # minLon > maxLon
        "27.5,41.6,30.2,40.4",  # minLat > maxLat
        "27.5,40.4,27.5,41.6",  # zero width
        "-181,40,30,41",
        "27,-91,30,41",
        "40.4,27.5,41.6,95",  # lat,lon swapped: 95 is not a latitude
        "",
    ],
)
def test_bbox_rejects(raw):
    with pytest.raises(ApiError) as exc:
        parse_bbox(raw)
    assert exc.value.code == "invalid_bbox"
    assert exc.value.status_code == 400


def test_unix_and_int():
    assert parse_unix("1791187200", "since") == 1791187200
    for bad in ["", "x", "1.5", "-1"]:
        with pytest.raises(ApiError) as exc:
            parse_unix(bad, "since")
        assert exc.value.code == "invalid_parameter"
        assert exc.value.details == {"parameter": "since"}
    assert parse_int("10", "bucket", minimum=1, maximum=600) == 10
    with pytest.raises(ApiError):
        parse_int("0", "bucket", minimum=1, maximum=600)
    with pytest.raises(ApiError):
        parse_int("601", "bucket", minimum=1, maximum=600)


def test_bool():
    assert parse_bool("true", "active") is True
    assert parse_bool("FALSE", "active") is False
    assert parse_bool("1", "active") is True
    with pytest.raises(ApiError):
        parse_bool("yes please", "active")


def test_csv_choices():
    allowed = {"large_airport", "medium_airport", "small_airport"}
    assert parse_csv_choices("large_airport, medium_airport", "type", allowed) == [
        "large_airport",
        "medium_airport",
    ]
    with pytest.raises(ApiError) as exc:
        parse_csv_choices("large_airport,heliport", "type", allowed)
    assert "heliport" in exc.value.message
