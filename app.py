from flask import Flask, request, jsonify, render_template
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import pandas as pd

app = Flask(__name__)

def calculate_rsi(data, window=14):
    """Calculate RSI indicator"""
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def generate_plot(data, ticker):
    """Generate a plot with price and RSI on the same time axis"""
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1], sharex=True)
    plt.subplots_adjust(hspace=0.1)  # Reduce space between subplots
    
    # Plot 1: Price and Moving Averages
    ax1.plot(data.index, data['Close'], label='Close Price', color='blue')
    ax1.plot(data.index, data['50_MA'], label='50-Day MA', color='orange', alpha=0.7)
    ax1.plot(data.index, data['100_MA'], label='100-Day MA', color='red', alpha=0.7)
    ax1.set_title(f'{ticker} Stock Price and Technical Indicators')
    ax1.set_ylabel('Price')
    ax1.grid(True)
    ax1.legend(loc='upper left')

    # Plot 2: RSI
    ax2.plot(data.index, data['RSI'], label='RSI', color='purple')
    ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)  # Overbought line
    ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)  # Oversold line
    ax2.set_ylabel('RSI')
    ax2.set_xlabel('Date')
    ax2.grid(True)
    ax2.set_ylim(0, 100)
    ax2.legend(loc='upper left')

    # Convert plot to base64 image
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    plt.close()
    
    return image_base64

@app.route('/stock', methods=['POST'])
def stock():
    ticker = request.form['ticker']
    start_date = request.form['start_date']
    period = request.form.get('period', '1y')

    try:
        stock_data = yf.download(ticker, start=start_date, period=period)
        if stock_data.empty:
            return jsonify({'error': 'No data found for the given ticker and date range.'}), 404

        stock_data['50_MA'] = stock_data['Close'].rolling(window=50).mean()
        stock_data['100_MA'] = stock_data['Close'].rolling(window=100).mean()
        stock_data['RSI'] = calculate_rsi(stock_data)

        highest_price = stock_data['High'].max()
        lowest_price = stock_data['Low'].min()

        plot_url = generate_plot(stock_data, ticker)

        return render_template('result.html', 
                             ticker=ticker, 
                             highest_price=highest_price,
                             lowest_price=lowest_price, 
                             plot_url=plot_url)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def process_single_stock(name_ticker_tuple, start_date, end_date):
    """Process a single stock's data"""
    name, ticker = name_ticker_tuple
    try:
        # Download stock data
        stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if stock_data.empty or len(stock_data) < 2:
            return None
        
        # Calculate basic metrics
        current_price = float(stock_data['Close'].iloc[-1])
        highest_price = float(stock_data['High'].max())
        gain_percentage = ((highest_price - current_price) / current_price) * 100
        
        # Calculate technical indicators
        stock_data['50_MA'] = stock_data['Close'].rolling(window=50).mean()
        stock_data['100_MA'] = stock_data['Close'].rolling(window=100).mean()
        stock_data['RSI'] = calculate_rsi(stock_data)
        
        # Get latest RSI value
        latest_rsi = float(stock_data['RSI'].dropna().iloc[-1]) if not stock_data['RSI'].dropna().empty else None
        
        return {
            'name': name,
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'highest_price': round(highest_price, 2),
            'gain_percentage': round(gain_percentage, 2),
            'rsi': round(latest_rsi, 2) if latest_rsi is not None else None,
            'stock_data': stock_data
        }
    except Exception as e:
        print(f"Error processing {ticker}: {str(e)}")
        return None

@app.route('/investment_opportunities', methods=['GET', 'POST'])
def investment_opportunities():
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        min_gain_percentage = float(request.form.get('min_gain_percentage', 13))
        
        # Collect all results in parallel
        all_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for name, ticker in nifty_50_tickers.items():
                future = executor.submit(process_single_stock, (name, ticker), start_date, end_date)
                futures.append(future)
            
            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    all_results.append(result)
        
        # Sort results by gain percentage
        sorted_results = sorted(all_results, key=lambda x: x['gain_percentage'], reverse=True)
        
        # Prepare summary of all stocks
        summary_table = []
        filtered_results = []
        
        for result in sorted_results:
            # Add to summary table
            summary_table.append({
                'name': result['name'],
                'ticker': result['ticker'],
                'current_price': result['current_price'],
                'highest_price': result['highest_price'],
                'gain_percentage': result['gain_percentage'],
                'rsi': result['rsi']
            })
            
            # If meets minimum gain criteria, generate plot and add to filtered results
            if result['gain_percentage'] >= min_gain_percentage:
                plot_url = generate_plot(result['stock_data'], result['ticker'])
                result_with_plot = result.copy()
                result_with_plot['plot_url'] = plot_url
                del result_with_plot['stock_data']  # Remove raw data before sending to template
                filtered_results.append(result_with_plot)
        
        return render_template(
            'investment_results.html',
            summary_table=summary_table,
            results=filtered_results,
            min_gain_percentage=min_gain_percentage
        )
    
    return render_template('investment_opportunities.html')


@app.route('/')
def home():
    return render_template('index.html')
nifty_50_tickers = {
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Axis Bank": "AXISBANK.NS",
    "Bajaj Auto": "BAJAJ-AUTO.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Bajaj Finserv": "BAJAJFINSV.NS",
    "BPCL": "BPCL.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Britannia": "BRITANNIA.NS",
    "Cipla": "CIPLA.NS",
    "Coal India": "COALINDIA.NS",
    "Divi's Laboratories": "DIVISLAB.NS",
    "Dr Reddy's Laboratories": "DRREDDY.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "Grasim Industries": "GRASIM.NS",
    "HCL Technologies": "HCLTECH.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "HDFC Life": "HDFCLIFE.NS",
    "Hero MotoCorp": "HEROMOTOCO.NS",
    "Hindalco Industries": "HINDALCO.NS",
    "Hindustan Unilever": "HINDUNILVR.NS",
    "HDFC": "HDFC.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Indian Oil Corporation": "IOC.NS",
    "IndusInd Bank": "INDUSINDBK.NS",
    "Infosys": "INFY.NS",
    "ITC": "ITC.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Kotak Mahindra Bank": "KOTAKBANK.NS",
    "Larsen & Toubro": "LT.NS",
    "Mahindra & Mahindra": "M&M.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Nestle India": "NESTLEIND.NS",
    "NTPC": "NTPC.NS",
    "ONGC": "ONGC.NS",
    "Power Grid Corporation": "POWERGRID.NS",
    "Reliance Industries": "RELIANCE.NS",
    "SBI Life Insurance": "SBILIFE.NS",
    "State Bank of India": "SBIN.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Tata Consultancy Services": "TCS.NS",
    "Tata Consumer Products": "TATACONSUM.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "Tech Mahindra": "TECHM.NS",
    "Titan Company": "TITAN.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "UPL": "UPL.NS",
    "Wipro": "WIPRO.NS"
}


if __name__ == '__main__':
    app.run(debug=True)
