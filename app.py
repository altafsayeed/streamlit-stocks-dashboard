import streamlit as st
import pandas as pd
import numpy as np
import requests
import tweepy
import config
import psycopg2, psycopg2.extras
import plotly.graph_objects as go

auth = tweepy.OAuthHandler(config.TWITTER_CONSUMER_KEY, config.TWITTER_CONSUMER_SECRET)
auth.set_access_token(config.TWITTER_ACCESS_TOKEN, config.TWITTER_ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

connection = psycopg2.connect(host=config.DB_HOST, database=config.DB_NAME, user=config.DB_USER, password=config.DB_PASS)
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

option = st.sidebar.selectbox("Which Dashboard would you like to view?", ('Twitter', 'Wallstreetbets', 'Stocktwits', 'Charts', 'Patterns'), 1)

st.header(option)


if option == 'Twitter':
    st.sidebar.text("View tweets from popular stock traders")
    st.sidebar.text("with charts from Finviz for technical")
    st.sidebar.text("analysis.")
    for username in config.TWITTER_USERNAMES:
        user = api.get_user(username)
        tweets = api.user_timeline(username)

        st.subheader(username)
        st.image(user.profile_image_url)

        for tweet in tweets:
            if '$' in tweet.text:
                words = tweet.text.split(' ')
                for word in words:
                    if word.startswith('$') and word[1:].isalpha():
                        symbol = word[1:]
                        st.write(symbol)
                        st.write(tweet.text)
                        st.image(f"https://finviz.com/chart.ashx?t={symbol}")


if option == 'Charts':
    st.sidebar.text("This stock database is populated only")
    st.sidebar.text("with stocks held by ARK Invest, so some")
    st.sidebar.text("stocks are not supported for charts,")
    st.sidebar.text("such as hype/meme stocks.")
    symbol = st.sidebar.text_input("Symbol", value='MSFT', max_chars=None, key=None, type='default')

    data = pd.read_sql("""
        select date(day) as day, open, high, low, close
        from daily_bars
        where stock_id = (select id from stock where UPPER(symbol) = %s LIMIT 1) 
        order by day asc""", connection, params=(symbol.upper(),))

    st.subheader(symbol.upper())

    fig = go.Figure(data=[go.Candlestick(x=data['day'],
                    open=data['open'],
                    high=data['high'],
                    low=data['low'],
                    close=data['close'],
                    name=symbol)])

    fig.update_xaxes(type='category')
    fig.update_layout(height=700)

    st.plotly_chart(fig, use_container_width=True)

    st.write(data)

if option == 'Wallstreetbets':
    st.sidebar.text("Most mentioned stocks on wallstreetbets")
    st.sidebar.text("View how many times a symbol has been")
    st.sidebar.text("mentioned, along with recent posts.")
    num_days = st.sidebar.slider('Filter by number of days ago:', 1, 7, 3)

    cursor.execute("""
        SELECT COUNT(*) AS num_mentions, symbol
        FROM mention JOIN stock ON stock.id = mention.stock_id
        WHERE date(dt) > current_date - interval '%s day'
        GROUP BY stock_id, symbol   
        HAVING COUNT(symbol) > 10
        ORDER BY num_mentions DESC
    """, (num_days,))

    counts = cursor.fetchall()
    for count in counts:
        st.write(count)
    
    cursor.execute("""
        SELECT symbol, message, url, dt
        FROM mention JOIN stock ON stock.id = mention.stock_id
        ORDER BY dt DESC
        LIMIT 100
    """)

    mentions = cursor.fetchall()
    for mention in mentions:
        st.text(mention['dt'])
        st.text(mention['symbol'])
        st.text(mention['message'])
        st.text(mention['url'])

    rows = cursor.fetchall()

    st.write(rows)

if option == 'Patterns':
    st.sidebar.text("Find stocks that showed bullish")
    st.sidebar.text("patterns recently using 1 day")
    st.sidebar.text("candlesticks. More patterns coming soon")
    pattern = st.sidebar.selectbox(
        "Which Pattern?",
        ("Bullish Engulfing", "3 Bar Breakout")
    )

    if pattern == 'Bullish Engulfing':
        cursor.execute("""
            SELECT * 
            FROM ( 
                SELECT day, open, close, stock_id, symbol, 
                LAG(close, 1) OVER ( PARTITION BY stock_id ORDER BY day ) previous_close, 
                LAG(open, 1) OVER ( PARTITION BY stock_id ORDER BY day ) previous_open 
                FROM daily_bars
                JOIN stock ON stock.id = daily_bars.stock_id
            ) a 
            WHERE previous_close < previous_open AND close > previous_open AND open < previous_close
            AND day > current_date - interval '10 days'
        """)

    if pattern == '3 Bar Breakout':
        cursor.execute("""
            SELECT DISTINCT * 
            FROM ( 
                SELECT day, close, volume, stock_id, symbol, 
                LAG(close, 1) OVER ( PARTITION BY stock_id ORDER BY day ) previous_close, 
                LAG(volume, 1) OVER ( PARTITION BY stock_id ORDER BY day ) previous_volume, 
                LAG(close, 2) OVER ( PARTITION BY stock_id ORDER BY day ) previous_previous_close, 
                LAG(volume, 2) OVER ( PARTITION BY stock_id ORDER BY day ) previous_previous_volume, 
                LAG(close, 3) OVER ( PARTITION BY stock_id ORDER BY day ) previous_previous_previous_close, 
                LAG(volume, 3) OVER ( PARTITION BY stock_id ORDER BY day ) previous_previous_previous_volume 
            FROM daily_bars 
            JOIN stock ON stock.id = daily_bars.stock_id) a 
            WHERE close > previous_previous_previous_close 
                AND previous_close < previous_previous_close 
                AND previous_close < previous_previous_previous_close 
                AND volume > previous_volume 
                AND previous_volume < previous_previous_volume 
                AND previous_previous_volume < previous_previous_previous_volume
                AND day > current_date - interval '31 days' 
        """)

    rows = cursor.fetchall()

    for row in rows:
        st.image(f"https://finviz.com/chart.ashx?t={row['symbol']}")

if option == 'Stocktwits':
    st.sidebar.text("See the latest stocktwits for any stock")
    symbol = st.sidebar.text_input("Search by Ticker Symbol", value='PLTR', max_chars=5)

    r = requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json")


    data = r.json()

    for message in data['messages']:
        st.image(message['user']['avatar_url'])
        st.write(message['user']['username'])
        st.write(message['created_at'])
        st.write(message['body'])


