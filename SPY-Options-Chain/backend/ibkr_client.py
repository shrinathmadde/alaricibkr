from ib_insync import *
import logging
import threading
import time
import datetime
import math
import asyncio
import nest_asyncio
from collections import defaultdict

# Assuming a config.py file exists with TWS_HOST, TWS_PORT, TWS_CLIENT_ID, REFRESH_RATE_MS
# Example:
class config: # Placeholder for your actual config module
    TWS_HOST = '127.0.0.1'
    TWS_PORT = 7496
    TWS_CLIENT_ID = 101 # Choose a unique ID
    REFRESH_RATE_MS = 5000 # 5 seconds


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Apply nest_asyncio if needed (e.g., for Flask, Jupyter)
# Make sure this is appropriate for your execution environment.
nest_asyncio.apply()

class IBKRClient:
    def __init__(self):
        self.ib = None
        self.connected = False
        self.options_data = defaultdict(dict)
        self.options_data_lock = threading.Lock()
        self.spy_price = 0.0
        self.update_thread = None
        self.running = False
        self.loop = None

    def connect(self):
        """Connect to TWS"""
        if self.connected:
            logger.info("Already connected.")
            return True
            
        try:
            logger.info(f"Attempting to connect to TWS on {config.TWS_HOST}:{config.TWS_PORT} with ClientID {config.TWS_CLIENT_ID}")
            
            # Setup our event loop for the background thread
            if self.loop is None or self.loop.is_closed():
                self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop) # Set as the current loop for this thread context
            
            self.ib = IB() # Create a new IB instance
            
            # Connect using ib.connect which can be run in a loop
            self.loop.run_until_complete(
                self.ib.connectAsync(
                    config.TWS_HOST, 
                    config.TWS_PORT, 
                    clientId=config.TWS_CLIENT_ID,
                    timeout=10 # Add a connection timeout
                )
            )
            
            self.connected = self.ib.isConnected()
            
            if self.connected:
                logger.info("Successfully connected to TWS.")
                self.running = True
                
                if self.update_thread is None or not self.update_thread.is_alive():
                    self.update_thread = threading.Thread(target=self._run_update_loop, name="IBKRUpdateThread", daemon=True)
                    self.update_thread.start()
                    logger.info("Update thread started.")
                return True
            else:
                logger.error("Failed to connect to TWS after async attempt.")
                self.ib = None # Clean up IB instance if connection failed
                return False
        except Exception as e:
            logger.error(f"Exception during TWS connection: {e}", exc_info=True)
            self.connected = False
            self.ib = None
            return False

    def disconnect(self):
        """Disconnect from TWS"""
        logger.info("Disconnect requested.")
        self.running = False # Signal the update loop to stop
        
        if self.update_thread and self.update_thread.is_alive():
            logger.info("Waiting for update thread to finish...")
            self.update_thread.join(timeout=config.REFRESH_RATE_MS / 1000 + 2) # Wait a bit longer than refresh cycle
            if self.update_thread.is_alive():
                logger.warning("Update thread did not finish in time.")
        
        if self.ib and self.ib.isConnected():
            logger.info("Disconnecting from TWS API.")
            self.ib.disconnect()
            
        self.connected = False
        self.ib = None # Clear IB instance
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop) # Request loop stop
            # Loop closure should ideally happen where it's run, or ensure it's cleaned up
        logger.info("Disconnected from TWS and resources cleaned.")

    def _run_update_loop(self):
        """Entry point for the thread that runs the asyncio event loop."""
        asyncio.set_event_loop(self.loop) # Ensure loop is set for this thread
        try:
            self.loop.run_until_complete(self._update_loop_async_tasks())
        except Exception as e:
            logger.error(f"Exception in _run_update_loop: {e}", exc_info=True)
        finally:
            if not self.loop.is_closed():
                self.loop.close()
            logger.info("Update loop and its asyncio event loop have finished.")


    async def _update_loop_async_tasks(self):
        """Manages periodic updates within the asyncio event loop."""
        logger.info("Async update task manager started.")
        while self.running:
            if not self.ib or not self.ib.isConnected():
                logger.warning("Not connected to TWS, attempting to reconnect or stopping updates.")
                # Optionally, add reconnect logic here or simply break if primary connection fails
                break # Or attempt self.connect() again carefully

            try:
                await self._update_spy_price_async()
                await self._update_options_chain_async()
            except ConnectionError: # More specific error for IB disconnections
                logger.error("Connection lost during update cycle. Attempting to handle.")
                self.connected = False # Mark as not connected
                # Potentially try to reconnect or signal main thread
                break 
            except Exception as e:
                logger.error(f"Unhandled error in async update cycle: {e}", exc_info=True)
            
            await asyncio.sleep(config.REFRESH_RATE_MS / 1000)
        logger.info("Async update task manager is stopping.")


    async def _update_spy_price_async(self):
        """Update current SPY price (async version)"""
        if not self.ib or not self.ib.isConnected():
            logger.warning("_update_spy_price_async: Not connected.")
            return
            
        try:
            spy_stock = Stock('SPY', 'SMART', 'USD')
            # Using await for qualifyContractsAsync which is the async version
            qualified_stocks = await self.ib.qualifyContractsAsync(spy_stock)
            
            if not qualified_stocks:
                logger.error("Failed to qualify SPY stock contract in _update_spy_price_async.")
                return
                
            spy_stock = qualified_stocks[0]
            
            # reqMktData is not async, it returns a Ticker object whose data updates
            ticker = self.ib.reqMktData(spy_stock, '', snapshot=True, regulatorySnapshot=False)
            
            await asyncio.sleep(0.5) # Increased sleep for snapshot data population for SPY
            
            new_price = 0.0
            if ticker.marketPrice(): # marketPrice() often gives a good usable price
                new_price = ticker.marketPrice()
            elif hasattr(ticker, 'last') and not math.isnan(ticker.last) and ticker.last > 0:
                new_price = ticker.last
            elif hasattr(ticker, 'close') and not math.isnan(ticker.close) and ticker.close > 0:
                new_price = ticker.close
            
            if new_price > 0:
                self.spy_price = new_price
                logger.debug(f"Updated SPY price: {self.spy_price:.2f}")
            else:
                logger.warning(f"Could not retrieve a valid SPY price. Ticker: {ticker}")
            
            self.ib.cancelMktData(spy_stock) # Crucial to avoid hitting data line limits
        except Exception as e:
            logger.error(f"Error updating SPY price: {e}", exc_info=True)

    async def _update_options_chain_async(self):
        """Update options chain data (async version) for today's expiry."""
        if not self.ib or not self.ib.isConnected():
            logger.warning("_update_options_chain_async: Not connected.")
            return
        if self.spy_price <= 0:
            logger.warning("_update_options_chain_async: SPY price is not valid, skipping options update.")
            return
            
        try:
            spy_stock = Stock('SPY', 'SMART', 'USD')
            # Ensure SPY stock is qualified (can be done once or checked if conId exists)
            if not spy_stock.conId: # If using a fresh spy_stock object each time
                 qualified_stocks = await self.ib.qualifyContractsAsync(spy_stock)
                 if not qualified_stocks:
                     logger.error("Failed to qualify SPY stock for options chain.")
                     return
                 spy_stock = qualified_stocks[0]
            
            chains = await self.ib.reqSecDefOptParamsAsync(
                spy_stock.symbol, '', spy_stock.secType, spy_stock.conId
            )
            
            if not chains:
                logger.error(f"No option chains parameters found for {spy_stock.symbol}.")
                return
                
            chain = next((c for c in chains if c.exchange == 'SMART'), chains[0]) # Prefer SMART
            
            # --- MODIFICATION FOR "TODAY'S" OPTIONS ---
            # For this example, "today" is May 14, 2025. In a live script, use datetime.datetime.now()
            current_processing_date = datetime.datetime(2025, 5, 14) # Set to current date for this context
            # To run for actual current day:
            # current_processing_date = datetime.datetime.now()
            target_expiry_date_str = current_processing_date.strftime('%Y%m%d')
            
            if target_expiry_date_str not in chain.expirations:
                logger.warning(f"No SPY options expiring today ({target_expiry_date_str}). Available: {chain.expirations[:5]}...")
                with self.options_data_lock:
                    if self.options_data: # Clear only if it has data
                        logger.info("Clearing stale options data as 0DTE is not available.")
                        self.options_data.clear()
                return # Do not proceed if today's expiry is not found
            
            logger.info(f"Fetching 0DTE options for SPY, Expiry: {target_expiry_date_str}, SPY Price: {self.spy_price:.2f}")
            
            all_strikes = sorted(list(set(chain.strikes))) # Use set to ensure unique strikes then sort
            if not all_strikes:
                logger.warning(f"No strikes available in the selected chain for {spy_stock.symbol}")
                return

            atm_strike = min(all_strikes, key=lambda x: abs(x - self.spy_price))
            
            strikes_around_atm_count = 10 # Number of strikes above and below ATM
            try:
                atm_index = all_strikes.index(atm_strike)
            except ValueError: # Should not happen if all_strikes is not empty
                logger.error(f"ATM strike {atm_strike} not found in strike list. Using SPY price as reference.")
                # Fallback: create strikes around self.spy_price if atm_strike logic fails
                # This part might need more robust handling if chain.strikes is unreliable
                atm_index = len(all_strikes) // 2 # Default to middle
            
            start_index = max(0, atm_index - strikes_around_atm_count)
            end_index = min(len(all_strikes), atm_index + strikes_around_atm_count + 1)
            selected_strikes = all_strikes[start_index:end_index]
            
            option_contracts = []
            for strike_val in selected_strikes:
                for right_val in ['C', 'P']:
                    contract = Option(
                        symbol='SPY',
                        lastTradeDateOrContractMonth=target_expiry_date_str, # Use the validated 0DTE
                        strike=strike_val,
                        right=right_val,
                        exchange=chain.exchange, # Use exchange from secDefOptParams
                        currency='USD',
                        tradingClass=chain.tradingClass # Important for uniqueness
                    )
                    option_contracts.append(contract)
            
            if not option_contracts:
                logger.info("No option contracts generated for fetching.")
                return

            qualified_options = await self.ib.qualifyContractsAsync(*option_contracts)
            # Filter out None results which can happen if a contract doesn't qualify
            qualified_options = [opt for opt in qualified_options if opt and opt.conId] 
            
            tickers_data = []
            # Request market data using reqMktData for snapshots
            for contract in qualified_options:
                ticker = self.ib.reqMktData(contract, '', snapshot=True, regulatorySnapshot=False)
                tickers_data.append(ticker) # Ticker object is added, its fields update
                await asyncio.sleep(0.05)  # Small delay to avoid flooding

            # Wait for data to arrive, adjust sleep based on number of contracts
            await asyncio.sleep(max(0.5, len(qualified_options) * 0.05)) 
            
            # Inside IBKRClient class, _update_options_chain_async method:

            # ... (after tickers_data has been populated by reqMktData calls and awaited) ...
            
            new_options_data = defaultdict(dict)
            for ticker in tickers_data:
                if not ticker.contract: 
                    logger.debug(f"Ticker with no contract info: {ticker}")
                    continue
                    
                strike = ticker.contract.strike
                right = ticker.contract.right
                
                # MODIFICATION: Use 'N/A' string for unavailable data
                bid_val = ticker.bid if hasattr(ticker, 'bid') and not math.isnan(ticker.bid) and ticker.bid != -1 else 'N/A'
                ask_val = ticker.ask if hasattr(ticker, 'ask') and not math.isnan(ticker.ask) and ticker.ask != -1 else 'N/A'
                
                # Store bid_val and ask_val directly (they will be float or 'N/A' string)
                key = f"{strike}_{right}"
                new_options_data[key] = {
                    "strike": float(strike),
                    "right": right,
                    "bid": bid_val,  # Will be float or 'N/A'
                    "ask": ask_val,  # Will be float or 'N/A'
                    "localSymbol": ticker.contract.localSymbol
                }
            
            with self.options_data_lock:
                self.options_data = new_options_data
            
            logger.info(f"Updated options data with {len(self.options_data)} contracts for {target_expiry_date_str}.")
            # ... (rest of the method, including cancelMktData) ...
            
            logger.info(f"Updated options data with {len(self.options_data)} contracts for {target_expiry_date_str}.")
            
            # Cancel market data requests
            for ticker in tickers_data:
                if ticker.contract: # Check again as contract might still be none if ticker didn't populate
                    self.ib.cancelMktData(ticker.contract)
                
        except Exception as e:
            logger.error(f"Error updating options chain: {e}", exc_info=True)

    def get_options_data(self):
        """Get current options data"""
        if not self.connected: # Simplified check
            logger.warning("get_options_data called while not connected.")
            return {"error": "Not connected to TWS", "spy_price": 0.0, "options": {}}
            
        with self.options_data_lock:
            # Create a deep copy if downstream modifies dicts, otherwise shallow is fine
            options_to_return = dict(self.options_data) 
            current_spy_price = self.spy_price
            
        if not options_to_return and current_spy_price <= 0: # No real data fetched yet
            logger.info("No valid live options data available, providing mock data if enabled or empty.")
            # return self._generate_mock_data() # Uncomment if mock data is desired fallback
            return {"spy_price": current_spy_price, "options": {}}

        return {
            "spy_price": current_spy_price,
            "options": options_to_return
        }

    def _generate_mock_data(self):
        """Generate mock options data for testing - kept from original for reference"""
        import random
        mock_spy_price = self.spy_price if self.spy_price > 0 else 500.0 # Adjusted mock SPY price
        mock_options = {}
        
        for i in range(-5, 6): # Mock 5 strikes above/below
            strike = round(mock_spy_price + i * 1.0) # Example strike step
            # Call option
            distance_from_strike = abs(strike - mock_spy_price)
            intrinsic_call = max(0, mock_spy_price - strike)
            extrinsic_call = max(0.05, 2.0 - distance_from_strike * 0.2 + random.uniform(-0.1, 0.1))
            call_bid = round(intrinsic_call + extrinsic_call, 2)
            call_ask = round(call_bid + max(0.01, random.uniform(0.01, 0.05) + distance_from_strike * 0.01), 2)

            mock_options[f"{strike}_C"] = {"strike": strike, "right": "C", "bid": call_bid, "ask": call_ask, "localSymbol": f"SPY {strike}C MOCK"}
            
            # Put option
            intrinsic_put = max(0, strike - mock_spy_price)
            extrinsic_put = max(0.05, 2.0 - distance_from_strike * 0.2 + random.uniform(-0.1, 0.1))
            put_bid = round(intrinsic_put + extrinsic_put, 2)
            put_ask = round(put_bid + max(0.01, random.uniform(0.01, 0.05) + distance_from_strike * 0.01), 2)
            mock_options[f"{strike}_P"] = {"strike": strike, "right": "P", "bid": put_bid, "ask": put_ask, "localSymbol": f"SPY {strike}P MOCK"}
        
        return {"spy_price": mock_spy_price, "options": mock_options}

    def refresh_options_data(self):
        """Placeholder for explicitly triggering a refresh if needed,
           though current design auto-refreshes."""
        if not self.running or not self.connected:
            logger.warning("Cannot refresh, not running or not connected.")
            return False
        logger.info("Data is auto-refreshed by background thread. Manual refresh not implemented beyond signaling.")
        # If an immediate refresh outside the timer is needed,
        # one could use asyncio.run_coroutine_threadsafe from another thread
        # or a queue to signal the asyncio loop.
        return True

# Singleton instance
ibkr_client = IBKRClient()

# Example Usage (for testing purposes, typically this class would be used by another part of your application)
if __name__ == '__main__':
    logger.info("IBKRClient Test Script Started")
    
    # util.patchAsyncio() # Only if using older ib_insync or specific environments like Spyder
    # util.startLoop() # Only if not managing loop explicitly or in Jupyter

    client = IBKRClient() # Use the global instance or a new one for isolated test
    
    try:
        if client.connect():
            logger.info("Successfully connected for test.")
            
            # Let it run for a few update cycles
            for i in range(5): # Example: 5 * REFRESH_RATE_MS
                time.sleep(config.REFRESH_RATE_MS / 1000)
                data = client.get_options_data()
                spy_px = data.get("spy_price", 0)
                opts_count = len(data.get("options", {}))
                logger.info(f"Test - Cycle {i+1}: SPY Price: {spy_px:.2f}, Options contracts fetched: {opts_count}")
                if opts_count > 0:
                    # Print a sample
                    sample_key = list(data["options"].keys())[0]
                    logger.info(f"Test - Sample Option ({sample_key}): {data['options'][sample_key]}")
                    break # Break after first successful data fetch for quick test
            
        else:
            logger.error("Test Script: Failed to connect to IBKR.")

    except KeyboardInterrupt:
        logger.info("Test script interrupted by user.")
    except Exception as e:
        logger.error(f"Error in test script: {e}", exc_info=True)
    finally:
        logger.info("Test script cleaning up...")
        client.disconnect()
        logger.info("Test script finished.")