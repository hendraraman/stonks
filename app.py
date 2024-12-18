from flask import Flask, request, jsonify, render_template
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import pandas as pd
import matplotlib
matplotlib.use('Agg') 

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
    # since we are using 100day ma, we add 100 days to the start date
    start_date = pd.to_datetime(start_date) - pd.Timedelta(days=100)

    try:
        stock_data = yf.download(ticker, start=start_date, period=period)
        if stock_data.empty:
            return jsonify({'error': 'No data found for the given ticker and date range.'}), 404

        stock_data['50_MA'] = stock_data['Close'].rolling(window=50).mean()
        stock_data['100_MA'] = stock_data['Close'].rolling(window=100).mean()
        # remove the first 100 days of data
        stock_data = stock_data[100:]
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
    """Process a single stock's data with improved error handling"""
    name, ticker = name_ticker_tuple
    start_date = pd.to_datetime(start_date) - pd.Timedelta(days=100)
    try:
        stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if stock_data.empty or len(stock_data) < 2:
            print(f"No data available for {ticker}")
            return None
        
        stock_data['50_MA'] = stock_data['Close'].rolling(window=50).mean()
        stock_data['100_MA'] = stock_data['Close'].rolling(window=100).mean()

        stock_data = stock_data[100:]
        
        # Calculate prices
        current_price = float(stock_data['Close'].iloc[-1])
        highest_price = float(stock_data['Close'].max())
        lowest_price = float(stock_data["Close"].min())
        
        # Validate prices
        if pd.isna(current_price) or pd.isna(highest_price):
            print(f"Invalid prices for {ticker}")
            return None
            
        discount_percentage = ((highest_price - current_price) / current_price) * 100
        lowest_closeness = ((current_price - lowest_price) / lowest_price) * 100

        # Calculate RSI
        stock_data['RSI'] = calculate_rsi(stock_data)
        latest_rsi = float(stock_data['RSI'].dropna().iloc[-1]) if not stock_data['RSI'].dropna().empty else None
        

        return {
            'name': name,
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'highest_price': round(highest_price, 2),
            'lowest_price': round(lowest_price, 2),
            'discount_percentage': round(discount_percentage, 2),
            'lowest_closeness': round(lowest_closeness, 2), 
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
        min_discount_percentage = float(request.form.get('min_discount_percentage', 13))
        
        # Process stocks sequentially
        all_results = []
        failed_tickers = []
        
        for name, ticker in nifty_50_tickers.items():
            try:
                result = process_single_stock((name, ticker), start_date, end_date)
                if result:
                    all_results.append(result)
                else:
                    failed_tickers.append(f"{name} ({ticker}) - No valid data")
            except Exception as e:
                failed_tickers.append(f"{name} ({ticker}) - Error: {str(e)}")
                continue
        
        sorted_results = sorted(all_results, key=lambda x: x['discount_percentage'], reverse=True)
        
        summary_table = []
        filtered_results = []
        
        # First prepare all summary data
        for result in sorted_results:
            summary_table.append({
                'name': result['name'],
                'ticker': result['ticker'],
                'current_price': result['current_price'],
                'highest_price': result['highest_price'],
                'discount_percentage': result['discount_percentage'],
                'lowest_closeness': result['lowest_closeness'],
                "absolute_difference": result["current_price"] - result["lowest_price"],
                'rsi': result['rsi']
            })
            
            # If meets minimum gain criteria, add to filtered results
            if result['discount_percentage'] >= min_discount_percentage:
                filtered_result = result.copy()
                filtered_result['plot_url'] = None  # Initially no plot
                filtered_result['stock_data'] = result['stock_data']
                filtered_results.append(filtered_result)

        # Generate plots only for the first two results
        for i in range(min(2, len(filtered_results))):
            try:
                plot_url = generate_plot(filtered_results[i]['stock_data'], filtered_results[i]['ticker'])
                filtered_results[i]['plot_url'] = plot_url
                del filtered_results[i]['stock_data']
            except Exception as e:
                failed_tickers.append(f"Error generating plot for {filtered_results[i]['ticker']}: {str(e)}")

        return render_template(
            'investment_results.html',
            summary_table=summary_table,
            results=filtered_results,
            min_discount_percentage=min_discount_percentage,
            start_date=start_date,
            end_date=end_date,
            failed_tickers=failed_tickers if failed_tickers else None
        )
    
    return render_template('investment_opportunities.html')

@app.route('/load_plot/<ticker>', methods=['POST'])
def load_plot(ticker):
    try:
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        
        # Get stock data and generate plot
        result = process_single_stock((ticker, ticker), start_date, end_date)
        if result and result['stock_data'] is not None:
            plot_url = generate_plot(result['stock_data'], ticker)
            return jsonify({'success': True, 'plot_url': plot_url})
        else:
            return jsonify({'success': False, 'error': 'No data available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# stock 101 static page
@app.route('/finance_101')
def finance_101():
    return render_template('finance_101.html')

@app.route('/')
def home():
    return render_template('index.html')


nifty_50_tickers = {
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Axis Bank": "AXISBANK.NS",
    "Appolo Hospitals Enterprise Ltd": "APOLLOHOSP.NS",
    "Bajaj Auto": "BAJAJ-AUTO.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Bajaj Finserv": "BAJAJFINSV.NS",
    "BPCL": "BPCL.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Britannia": "BRITANNIA.NS",
    "Bharat Electronics Ltd ": "BEL.NS",
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
    "Shriram Finance Ltd": "SHRIRAMFIN.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Tata Consultancy Services": "TCS.NS",
    "Tata Consumer Products": "TATACONSUM.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "Tech Mahindra": "TECHM.NS",
    "Titan Company": "TITAN.NS",
    "Trent Ltd": "TRENT.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "UPL": "UPL.NS",
    "Wipro": "WIPRO.NS"
}


if __name__ == '__main__':
    app.run(debug=True)


"""  
1: nifty dict be variable
2: also consider diff btw hightest and lowest  and make a filter for that
3: look for stocks closer to its lowest price and include it as gain percentage
4: current gain perc is discount perc wrt to highest price

"""