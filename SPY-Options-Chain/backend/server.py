from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import logging
import threading
import time
# Assuming config.py with FRONTEND_URL, REFRESH_RATE_MS, API_HOST, API_PORT
import config # Make sure this contains API_HOST and API_PORT
from ibkr_client import ibkr_client # Your existing IBKRClient class
from order_routes import handle_place_order # Assuming this is correctly set up

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": config.FRONTEND_URL}})
socketio = SocketIO(app, cors_allowed_origins=config.FRONTEND_URL, async_mode='threading') # explicitly use threading async_mode

# Register order routes
handle_place_order(app)

# Global variable to control background thread for emitting socket data
socket_emitter_thread_running = False
socket_emitter_thread = None


def options_data_emitter_task():
    """Background task to periodically send options data to clients via Socket.IO"""
    global socket_emitter_thread_running
    logger.info("Socket.IO options data emitter task started.")
    
    while socket_emitter_thread_running:
        try:
            # Inside server.py, options_data_emitter_task function:

            if ibkr_client.connected and ibkr_client.running:
                options_data = ibkr_client.get_options_data()
                
                if options_data and isinstance(options_data, dict) and \
                   'spy_price' in options_data and 'options' in options_data: # Removed detailed content check, rely on get_options_data
                    
                    options_dict_to_emit = options_data.get('options', {})
                    spy_price_to_emit = options_data.get('spy_price', 0.0)

                    # --- START ENHANCED LOGGING before emit ---
                    logger.info(
                        f"Socket.IO Emitter: About to emit 'options_update'. "
                        f"SPY Price={spy_price_to_emit}, "
                        f"Options Count={len(options_dict_to_emit)}"
                    )
                    
                    num_na_bids = 0
                    num_na_asks = 0
                    first_few_options_logged = 0
                    if options_dict_to_emit: # Check if there are any options
                        for key, opt_detail in options_dict_to_emit.items():
                            if isinstance(opt_detail, dict): # Check if opt_detail is a dictionary
                                if opt_detail.get('bid') == 'N/A':
                                    num_na_bids += 1
                                if opt_detail.get('ask') == 'N/A':
                                    num_na_asks += 1
                                if first_few_options_logged < 3: # Log details of first few options
                                    logger.info(f"Socket.IO Emitter Sample: Key='{key}', Data={opt_detail}")
                                    first_few_options_logged += 1
                            else:
                                logger.warning(f"Socket.IO Emitter: Encountered non-dict item in options_dict_to_emit for key {key}: {opt_detail}")

                        logger.info(
                            f"Socket.IO Emitter: Stats for options to be emitted - "
                            f"N/A Bids: {num_na_bids}/{len(options_dict_to_emit)}, "
                            f"N/A Asks: {num_na_asks}/{len(options_dict_to_emit)}"
                        )
                    else:
                        logger.info("Socket.IO Emitter: No options data to emit in this cycle (options_dict_to_emit is empty).")
                    # --- END ENHANCED LOGGING ---
                    
                    socketio.emit('options_update', options_data) # Send the original structure
                # ... (rest of the task) ...
                elif ibkr_client.connected: # Connected but data might not be ready (e.g. SPY price 0)
                    logger.info(f"Socket.IO Emitter: IBKRClient connected, but data not ready for emit. SPY Price: {options_data.get('spy_price', 'N/A')}, Options: {len(options_data.get('options', {}))} items.")
                # If not connected or data is invalid, get_options_data already logs this
            else:
                logger.info("Socket.IO Emitter: IBKRClient not connected or not running. Skipping emit.")

            socketio.sleep(config.REFRESH_RATE_MS / 1000) # Use socketio.sleep for background tasks
            
            # The ibkr_client.refresh_options_data() method in your IBKRClient
            # currently just logs. The actual data refresh happens within IBKRClient's own loop.
            # So, calling it here is mostly for logging from this thread's perspective.
            # If you needed to force an out-of-cycle refresh, IBKRClient would need a different mechanism.
            # ibkr_client.refresh_options_data() # This can be removed if it's just logging
            
        except Exception as e:
            logger.error(f"Error in options_data_emitter_task: {e}", exc_info=True)
            socketio.sleep(config.REFRESH_RATE_MS / 1000) # Sleep even on error to prevent tight loop
            
    logger.info("Socket.IO options data emitter task stopped.")

@socketio.on('connect')
def handle_connect():
    """Handle client connection for Socket.IO"""
    global socket_emitter_thread_running, socket_emitter_thread
    logger.info(f"Socket.IO client connected: {threading.get_ident()}") # Log thread ID
    
    # Start background thread for emitting options data if not already running
    if not socket_emitter_thread_running:
        socket_emitter_thread_running = True
        socket_emitter_thread = socketio.start_background_task(target=options_data_emitter_task)
        logger.info("Started Socket.IO options data emitter background task.")
    # Send initial data immediately if available
    if ibkr_client.connected and ibkr_client.running:
        initial_data = ibkr_client.get_options_data()
        if initial_data.get('spy_price',0) > 0 and len(initial_data.get('options',{}))>0:
             socketio.emit('options_update', initial_data)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection for Socket.IO"""
    logger.info(f"Socket.IO client disconnected: {threading.get_ident()}")
    # Consider stopping the emitter if no clients are connected, though it's often left running.
    # If you want to stop it when the last client disconnects:
    # if not socketio.server.eio.clients: # Check if any clients remain
    #     global socket_emitter_thread_running
    #     socket_emitter_thread_running = False
    #     logger.info("Last Socket.IO client disconnected, stopping emitter task.")


@app.route('/api/connect', methods=['POST'])
def connect_to_tws_route(): # Renamed to avoid conflict if "connect" is a common name
    """API endpoint to connect to TWS"""
    try:
        logger.info("/api/connect called")
        success = ibkr_client.connect() # This starts IBKRClient's internal update loop
        if success:
            return jsonify({"success": True, "message": "Connection process initiated/successful."})
        else:
            return jsonify({"success": False, "message": "Failed to connect to TWS or already connected and failed."}), 500
    except Exception as e:
        logger.error(f"Error in /api/connect: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/disconnect', methods=['POST'])
def disconnect_from_tws_route(): # Renamed
    """API endpoint to disconnect from TWS"""
    try:
        logger.info("/api/disconnect called")
        ibkr_client.disconnect()
        # Also stop the socket emitter if it's running
        global socket_emitter_thread_running
        socket_emitter_thread_running = False
        return jsonify({"success": True, "message": "Disconnected from TWS."})
    except Exception as e:
        logger.error(f"Error in /api/disconnect: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/options', methods=['GET'])
def get_options_http(): # Renamed
    """API endpoint to get current options data via HTTP GET"""
    try:
        # ibkr_client.running is set by IBKRClient after its TWS connection
        # ibkr_client.connected is also a good check
        if not (ibkr_client.connected and ibkr_client.running):
            logger.warning("/api/options: IBKRClient not connected or not running.")
            return jsonify({"error": "Not connected to TWS or data fetcher not running"}), 503 # Service Unavailable
            
        options_data = ibkr_client.get_options_data()
        
        # Log before returning via HTTP
        logger.info(
            f"/api/options: Returning SPY Price={options_data.get('spy_price')}, "
            f"Options Count={len(options_data.get('options', {}))}"
        )
        if len(options_data.get('options', {})) > 0:
            sample_key = list(options_data.get('options', {}).keys())[0]
            logger.debug(f"/api/options: Sample content for key '{sample_key}': {options_data.get('options', {})[sample_key]}")
            
        return jsonify(options_data)
    except Exception as e:
        logger.error(f"Error in /api/options: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Inside server.py
@app.route('/api/status', methods=['GET'])
def get_status_route(): # Renamed from get_status to avoid potential conflicts
    """API endpoint to get TWS connection status and SPY price"""
    try:
        is_ibkr_connected = ibkr_client.connected and ibkr_client.running
        # Access spy_price directly from the ibkr_client instance
        current_spy_price = ibkr_client.spy_price if is_ibkr_connected and ibkr_client.spy_price > 0 else 0.0
        
        status_payload = {
            "ibkr_connected": is_ibkr_connected,
            "spy_price": current_spy_price
        }
        # Use the logger from your __main__ context or app.logger
        logger.info(f"/api/status returning: {status_payload}") 
        return jsonify(status_payload)
    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True) # Added exc_info
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # It's good practice for IBKRClient connection to be initiated explicitly,
    # e.g., after the server starts or via an API call, rather than globally on module import.
    # The current IBKRClient is a global singleton; Flask's debug reloader might interact oddly with this.
    # For production, avoid Flask debug mode with global state like this.
    
    # The IBKRClient's internal update loop for fetching data from TWS is started
    # within its own connect() method.
    # The options_data_emitter_task is started when the first socket client connects.

    logger.info(f"Starting Flask server on {config.API_HOST}:{config.API_PORT}")
    # socketio.run will block here. IBKR connection should be triggered (e.g. by frontend calling /api/connect)
    # or you can initiate it programmatically after server starts if desired, but carefully.
    socketio.run(app, host=config.API_HOST, port=config.API_PORT, debug=True, use_reloader=False)
    # Added use_reloader=False to simplify debugging with the global ibkr_client instance.
    # The Flask auto-reloader can cause issues with background threads and singletons.