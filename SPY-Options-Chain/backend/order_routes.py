from flask import jsonify, request
import logging
import datetime
import json
from order_manager import OrderManager
from ibkr_client import ibkr_client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create order manager instance
# Updated to use ibkr_client directly (not ibkr_client.api)
order_manager = OrderManager(ibkr_client)

def handle_place_order(app):
    """Register order placement routes with the Flask app"""
    
    @app.route('/api/place_single_order', methods=['POST'])
    def place_single_order():
        """API endpoint to place a single option order"""
        try:
            order_data = request.json
            logger.info(f"Received single order: {order_data}")
            
            # Validate order data
            required_fields = ["symbol", "expiry", "strike", "right", "action", "quantity"]
            for field in required_fields:
                if field not in order_data:
                    return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
            
            # Place order
            result = order_manager.place_single_order(order_data)
            
            if result["success"]:
                return jsonify(result)
            else:
                return jsonify(result), 500
                
        except Exception as e:
            logger.error(f"Error placing single order: {e}")
            return jsonify({"success": False, "message": str(e)}), 500
    
    @app.route('/api/place_multi_leg_order', methods=['POST'])
    def place_multi_leg_order():
        """API endpoint to place a multi-leg option order"""
        try:
            order_data = request.json
            logger.info(f"Received multi-leg order: {order_data}")
            
            # Validate order data
            if "legs" not in order_data or not isinstance(order_data["legs"], list) or len(order_data["legs"]) == 0:
                return jsonify({"success": False, "message": "Missing or invalid 'legs' field"}), 400
                
            # Validate each leg
            required_fields = ["symbol", "expiry", "strike", "right", "action", "quantity"]
            for i, leg in enumerate(order_data["legs"]):
                for field in required_fields:
                    if field not in leg:
                        return jsonify({"success": False, "message": f"Missing required field '{field}' in leg {i}"}), 400
            
            # Place multi-leg order
            result = order_manager.place_multi_leg_order(order_data["legs"])
            
            if result["success"]:
                return jsonify(result)
            else:
                return jsonify(result), 500
                
        except Exception as e:
            logger.error(f"Error placing multi-leg order: {e}")
            return jsonify({"success": False, "message": str(e)}), 500
    
    @app.route('/api/cancel_order/<int:order_id>', methods=['POST'])
    def cancel_order(order_id):
        """API endpoint to cancel an order"""
        try:
            logger.info(f"Cancelling order {order_id}")
            
            # Cancel order
            result = order_manager.cancel_order(order_id)
            
            if result["success"]:
                return jsonify(result)
            else:
                return jsonify(result), 404
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return jsonify({"success": False, "message": str(e)}), 500
    
    @app.route('/api/order_status/<int:order_id>', methods=['GET'])
    def get_order_status(order_id):
        """API endpoint to get order status"""
        try:
            logger.info(f"Getting status for order {order_id}")
            
            # Get order status
            result = order_manager.get_order_status(order_id)
            
            if result["success"]:
                return jsonify(result)
            else:
                return jsonify(result), 404
                
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return jsonify({"success": False, "message": str(e)}), 500

    logger.info("Registered order routes")