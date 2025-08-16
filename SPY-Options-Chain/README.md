# SPY Options Chain Application

This application displays the SPY options chain with real-time data from Interactive Brokers TWS (Trader Workstation), focusing on 0DTE (zero days to expiration) options. The application provides bid/ask prices and allows for multiple-leg order placement directly from the options chain.

## Features

- Real-time options data from IBKR TWS
- Display of SPY 0DTE options chain
- Automatic updates without page refresh
- Single-leg order placement
- Multi-leg order creation and submission
- In-the-money highlighting

## Project Structure

The project is divided into two main parts:

### Backend (Python)

- Flask-based API server
- WebSocket for real-time updates
- TWS API integration

### Frontend (React)

- Interactive options chain table
- Order placement forms
- Real-time data display

## Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm 8+
- Interactive Brokers Trader Workstation (TWS)

### Backend Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the backend server:
   ```
   ./start_backend.sh  # On Windows: start_backend.bat
   ```

### Frontend Setup

1. Install dependencies:
   ```
   npm install
   ```

2. Start the React development server:
   ```
   ./start_frontend.sh  # On Windows: start_frontend.bat
   ```

## TWS Configuration

1. Launch TWS or IB Gateway
2. Go to File > Global Configuration > API > Settings
3. Enable "Socket port" and set it to 7497 (demo) or 7496 (live)
4. Check "Enable ActiveX and Socket Clients"
5. Add your IP to the "Trusted IPs" list or check "Allow connections from localhost only"

## Usage

1. Start TWS and log in to your account
2. Start the backend server
3. Start the frontend application
4. Connect to TWS using the "Connect" button
5. View the options chain and place orders

## Files Overview

### Backend

- `config.py`: Configuration settings
- `server.py`: Main Flask application
- `ibkr_client.py`: TWS API client
- `order_manager.py`: Order handling logic
- `order_routes.py`: API routes for orders

### Frontend

- `src/components/App.js`: Main React component
- `src/components/OptionsTable.js`: Options chain display
- `src/components/OrderForm.js`: Single-leg order form
- `src/components/MultiLegOrderForm.js`: Multi-leg order form
- `src/services/ApiService.js`: Backend API client
- `src/services/SocketService.js`: WebSocket client

## Important Notes

- Make sure TWS is running before connecting the application
- The application is set up for demo/paper trading by default; adjust the port in `config.py` for live trading
- For live trading, review the order placement code carefully and test thoroughly in a paper trading environment first

## Troubleshooting

- If connection to TWS fails, check that TWS is running and API access is enabled
- Verify the port numbers in `config.py` match your TWS settings
- Check console logs for any error messages