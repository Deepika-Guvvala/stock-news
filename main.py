STOCK = "TSLA"
COMPANY_NAME = "Tesla Inc"

import os
import requests

ALPHA_VANTAGE_API_KEY = os.environ["ALPHA_VANTAGE_API_KEY"]
NEWS_API_KEY = os.environ["NEWS_API_KEY"]
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]


def get_stock_prices():
    """Returns (yesterday_close, day_before_close) as floats."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "apikey": ALPHA_VANTAGE_API_KEY,
        "symbol": STOCK,
        "datatype": "JSON",
    }
    response = requests.get("https://www.alphavantage.co/query", params=params)
    response.raise_for_status()
    data = response.json()
    time_series = data["Time Series (Daily)"]
    dates = sorted(time_series.keys(), reverse=True)
    yesterday_close = float(time_series[dates[0]]["4. close"])
    day_before_close = float(time_series[dates[1]]["4. close"])
    return yesterday_close, day_before_close


def calculate_percentage_change(yesterday, day_before):
    """Returns signed percentage change from day_before to yesterday."""
    return round((yesterday - day_before) / day_before * 100, 2)


def get_news(company_name):
    """Returns list of up to 3 article dicts with 'title' and 'description'."""
    params = {
        "apiKey": NEWS_API_KEY,
        "qInTitle": company_name,
    }
    response = requests.get("https://newsapi.org/v2/everything", params=params)
    response.raise_for_status()
    articles = response.json().get("articles", [])
    return [{"title": a["title"], "description": a["description"]} for a in articles[:3]]


def format_message(stock, percentage, article):
    """Returns a formatted SMS string for one article."""
    arrow = "🔺" if percentage > 0 else "🔻"
    return (
        f"{stock}: {arrow}{abs(percentage)}%\n"
        f"Headline: {article['title']}\n"
        f"Brief: {article['description']}"
    )


def send_email(subject, body):
    import smtplib
    with smtplib.SMTP("smtp.gmail.com", 587) as connection:
        connection.starttls()
        connection.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        connection.sendmail(
            from_addr=EMAIL_ADDRESS,
            to_addrs=EMAIL_TO,
            msg=f"Subject:{subject}\n\n{body}",
        )


if __name__ == "__main__":
    yesterday, day_before = get_stock_prices()
    pct = calculate_percentage_change(yesterday, day_before)

    if abs(pct) >= 5:
        articles = get_news(COMPANY_NAME)
        for article in articles:
            msg = format_message(STOCK, pct, article)
            send_email(subject=f"{STOCK} Stock Alert", body=msg)
            print(msg)
