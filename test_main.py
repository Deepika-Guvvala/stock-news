import pytest
from unittest.mock import patch, MagicMock
import main


MOCK_ALPHA_VANTAGE_RESPONSE = {
    "Meta Data": {"2. Symbol": "TSLA"},
    "Time Series (Daily)": {
        "2024-01-05": {"4. close": "230.00"},
        "2024-01-04": {"4. close": "200.00"},
        "2024-01-03": {"4. close": "195.00"},
    },
}

MOCK_NEWS_RESPONSE = {
    "articles": [
        {"title": "Tesla Q4 Results", "description": "Tesla beats expectations."},
        {"title": "Tesla FSD Update", "description": "Full self-driving update released."},
        {"title": "Tesla Model Y", "description": "New Model Y variant announced."},
        {"title": "Tesla Gigafactory", "description": "New factory opens in Texas."},
    ]
}


# --- get_stock_prices ---

class TestGetStockPrices:
    def _mock_get(self, json_data):
        mock_resp = MagicMock()
        mock_resp.json.return_value = json_data
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_returns_yesterday_and_day_before_close(self):
        with patch("main.requests.get", return_value=self._mock_get(MOCK_ALPHA_VANTAGE_RESPONSE)):
            yesterday, day_before = main.get_stock_prices()
        assert yesterday == 230.00
        assert day_before == 200.00

    def test_returns_floats(self):
        with patch("main.requests.get", return_value=self._mock_get(MOCK_ALPHA_VANTAGE_RESPONSE)):
            yesterday, day_before = main.get_stock_prices()
        assert isinstance(yesterday, float)
        assert isinstance(day_before, float)

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 403")
        with patch("main.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="HTTP 403"):
                main.get_stock_prices()

    def test_uses_two_most_recent_dates(self):
        # Ensures the function picks the two latest dates regardless of dict order
        data = {
            "Meta Data": {},
            "Time Series (Daily)": {
                "2024-01-01": {"4. close": "100.00"},
                "2024-01-03": {"4. close": "120.00"},
                "2024-01-02": {"4. close": "110.00"},
            },
        }
        with patch("main.requests.get", return_value=self._mock_get(data)):
            yesterday, day_before = main.get_stock_prices()
        assert yesterday == 120.00
        assert day_before == 110.00


# --- calculate_percentage_change ---

class TestCalculatePercentageChange:
    def test_positive_change(self):
        assert main.calculate_percentage_change(210, 200) == 5.0

    def test_negative_change(self):
        assert main.calculate_percentage_change(190, 200) == -5.0

    def test_no_change(self):
        assert main.calculate_percentage_change(200, 200) == 0.0

    def test_rounding(self):
        result = main.calculate_percentage_change(101, 300)
        assert result == round((101 - 300) / 300 * 100, 2)

    def test_large_increase(self):
        assert main.calculate_percentage_change(300, 100) == 200.0


# --- get_news ---

class TestGetNews:
    def _mock_get(self, json_data):
        mock_resp = MagicMock()
        mock_resp.json.return_value = json_data
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_returns_at_most_three_articles(self):
        with patch("main.requests.get", return_value=self._mock_get(MOCK_NEWS_RESPONSE)):
            articles = main.get_news("Tesla Inc")
        assert len(articles) == 3

    def test_article_has_title_and_description(self):
        with patch("main.requests.get", return_value=self._mock_get(MOCK_NEWS_RESPONSE)):
            articles = main.get_news("Tesla Inc")
        for article in articles:
            assert "title" in article
            assert "description" in article

    def test_article_content_matches_source(self):
        with patch("main.requests.get", return_value=self._mock_get(MOCK_NEWS_RESPONSE)):
            articles = main.get_news("Tesla Inc")
        assert articles[0]["title"] == "Tesla Q4 Results"
        assert articles[0]["description"] == "Tesla beats expectations."

    def test_fewer_than_three_articles(self):
        data = {"articles": [{"title": "Only One", "description": "Just one article."}]}
        with patch("main.requests.get", return_value=self._mock_get(data)):
            articles = main.get_news("Tesla Inc")
        assert len(articles) == 1

    def test_empty_articles(self):
        with patch("main.requests.get", return_value=self._mock_get({"articles": []})):
            articles = main.get_news("Tesla Inc")
        assert articles == []

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 401")
        with patch("main.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="HTTP 401"):
                main.get_news("Tesla Inc")


# --- format_message ---

class TestFormatMessage:
    def test_upward_arrow_for_positive_change(self):
        article = {"title": "Tesla rises", "description": "Stock up today."}
        msg = main.format_message("TSLA", 6.0, article)
        assert "🔺" in msg
        assert "🔻" not in msg

    def test_downward_arrow_for_negative_change(self):
        article = {"title": "Tesla falls", "description": "Stock down today."}
        msg = main.format_message("TSLA", -6.0, article)
        assert "🔻" in msg
        assert "🔺" not in msg

    def test_message_contains_stock_symbol(self):
        article = {"title": "Headline", "description": "Desc"}
        msg = main.format_message("TSLA", 5.0, article)
        assert "TSLA" in msg

    def test_message_contains_absolute_percentage(self):
        article = {"title": "Headline", "description": "Desc"}
        msg = main.format_message("TSLA", -7.5, article)
        assert "7.5%" in msg
        assert "-7.5%" not in msg

    def test_message_contains_headline_and_brief(self):
        article = {"title": "Big News", "description": "Details here."}
        msg = main.format_message("TSLA", 5.0, article)
        assert "Headline: Big News" in msg
        assert "Brief: Details here." in msg

    def test_format_structure(self):
        article = {"title": "T", "description": "D"}
        msg = main.format_message("TSLA", 5.0, article)
        lines = msg.split("\n")
        assert lines[0].startswith("TSLA:")
        assert lines[1].startswith("Headline:")
        assert lines[2].startswith("Brief:")


# --- send_email ---

class TestSendEmail:
    def _make_smtp_mock(self):
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        return mock_smtp

    def test_connects_to_gmail_smtp(self):
        mock_smtp = self._make_smtp_mock()
        with patch("smtplib.SMTP", return_value=mock_smtp) as mock_smtp_cls:
            main.send_email("Subject", "Body")
        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587)

    def test_calls_starttls(self):
        mock_smtp = self._make_smtp_mock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            main.send_email("Subject", "Body")
        mock_smtp.starttls.assert_called_once()

    def test_logs_in_with_credentials(self):
        mock_smtp = self._make_smtp_mock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.object(main, "EMAIL_ADDRESS", "sender@gmail.com"):
                with patch.object(main, "EMAIL_PASSWORD", "secret"):
                    main.send_email("Subject", "Body")
        mock_smtp.login.assert_called_once_with("sender@gmail.com", "secret")

    def test_sends_to_correct_recipient(self):
        mock_smtp = self._make_smtp_mock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.object(main, "EMAIL_ADDRESS", "sender@gmail.com"):
                with patch.object(main, "EMAIL_TO", "recipient@gmail.com"):
                    main.send_email("Subject", "Body")
        _, kwargs = mock_smtp.sendmail.call_args
        assert kwargs.get("to_addrs") == "recipient@gmail.com"

    def test_email_contains_subject_and_body(self):
        mock_smtp = self._make_smtp_mock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            main.send_email("Stock Alert", "TSLA is up 6%")
        _, kwargs = mock_smtp.sendmail.call_args
        msg = kwargs.get("msg")
        assert "Subject:Stock Alert" in msg
        assert "TSLA is up 6%" in msg
