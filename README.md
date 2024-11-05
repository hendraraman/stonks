# NIFTY 50 Investment Analysis App

This application provides an investment analysis tool for NIFTY 50 stocks, allowing users to analyze stock performance and technical indicators like RSI and moving averages. The application is built with Flask and uses Yahoo Finance data to generate stock insights.

## Features

- Analyze stocks from the NIFTY 50 list.
- Fetch historical stock data from Yahoo Finance.
- Calculate technical indicators such as the RSI (Relative Strength Index), 50-day, and 100-day moving averages.
- Visualize stock data with price and RSI plots.
- Filter stocks based on minimum potential gain percentage.
- Display a detailed analysis of selected stocks, including technical charts.

## Directory Structure

```plaintext
├── .git/
├── templates/
│   ├── index.html
│   ├── investment_opportunities.html
│   ├── investment_results.html
│   └── result.html
├── README.md
├── app.py
└── requirements.txt
```

## Install the required dependencies:

pip install -r requirements.txt


## Run the application:

python app.py
