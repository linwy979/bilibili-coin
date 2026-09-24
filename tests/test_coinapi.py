from unittest.mock import MagicMock
import coinapi

API_DATA = {
    "bitcoin": {"usd": 101000}, "ethereum": {"usd": 2600}, "tether": {"usd": 1},
    "ripple": {"usd": 2.1}, "binancecoin": {"usd": 650}, "solana": {"usd": 150},
    "usd-coin": {"usd": 1}, "dogecoin": {"usd": 0.19},
}


def fake_get(data):
    return MagicMock(return_value=MagicMock(status_code=200, json=lambda: data))


def test_fetch_and_save_writes_price_and_history(monkeypatch, sql):
    monkeypatch.setattr(coinapi.requests, "get", fake_get(API_DATA))
    coinapi.fetch_and_save()
    prices = {r["coin_id"]: r["price"] for r in sql("SELECT coin_id, price FROM price")}
    assert len(prices) == 8 and prices["BTC"] == 101000
    assert sql("SELECT COUNT(*) AS n FROM price_history")[0]["n"] == 8

    coinapi.fetch_and_save()  # 同一分鐘再跑一次不應重複或出錯
    assert sql("SELECT COUNT(*) AS n FROM price_history")[0]["n"] == 8


def test_new_coin_from_admin_is_fetched(monkeypatch, sql):
    sql("INSERT INTO coin_list VALUES ('ADA', 'cardano')")
    get = fake_get({**API_DATA, "cardano": {"usd": 0.7}})
    monkeypatch.setattr(coinapi.requests, "get", get)
    coinapi.fetch_and_save()
    assert "cardano" in get.call_args.kwargs["params"]["ids"]
    assert sql("SELECT price FROM price WHERE coin_id='ADA'")[0]["price"] == 0.7


def test_missing_coin_in_response_is_skipped(monkeypatch, sql):
    partial = {"bitcoin": {"usd": 1}}
    monkeypatch.setattr(coinapi.requests, "get", fake_get(partial))
    coinapi.fetch_and_save()
    assert [r["coin_id"] for r in sql("SELECT coin_id FROM price WHERE price = 1")] == ["BTC"]


def test_api_error_does_not_crash(monkeypatch, sql):
    monkeypatch.setattr(coinapi.requests, "get", MagicMock(return_value=MagicMock(status_code=429, text="rate limited")))
    coinapi.fetch_and_save()
    assert sql("SELECT COUNT(*) AS n FROM price_history")[0]["n"] == 0
