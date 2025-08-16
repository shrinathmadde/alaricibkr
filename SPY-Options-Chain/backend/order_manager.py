from ib_insync import *
import logging
import json
from ibkr_client import ibkr_client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, client):
        self.client = client
        self.orders = {}  # Dictionary to track orders by order ID

    def create_option_contract(self, symbol, expiry, strike, right):
        """Create an option contract"""
        # With ib_insync, we need to qualify contracts first
        contract = Option(
            symbol=symbol,
            lastTradeDateOrContractMonth=expiry,
            strike=strike,
            right=right,
            exchange='SMART',
            currency='USD'
        )
        
        # Try to qualify the contract
        try:
            qualified_contracts = self.client.ib.qualifyContracts(contract)
            if qualified_contracts:
                return qualified_contracts[0]
            else:
                logger.error(f"Failed to qualify contract: {symbol} {expiry} {strike} {right}")
                return None
        except Exception as e:
            logger.error(f"Error qualifying contract: {e}")
            return None

    def create_market_order(self, action, quantity):
        """Create a simple market order"""
        order = MarketOrder(
            action=action,  # "BUY" or "SELL"
            totalQuantity=quantity
        )
        return order

    def create_limit_order(self, action, quantity, limit_price):
        """Create a limit order"""
        order = LimitOrder(
            action=action,  # "BUY" or "SELL"
            totalQuantity=quantity,
            lmtPrice=limit_price
        )
        return order

    def place_single_order(self, order_details):
        """Place a single option order"""
        try:
            if not self.client.connected:
                return {"success": False, "message": "Not connected to TWS"}
                
            # Create and qualify contract
            contract = self.create_option_contract(
                order_details["symbol"],
                order_details["expiry"],
                order_details["strike"],
                order_details["right"]
            )
            
            if not contract:
                return {"success": False, "message": "Failed to create valid contract"}
            
            # Create order
            if order_details["order_type"] == "MARKET":
                order = self.create_market_order(
                    order_details["action"],
                    order_details["quantity"]
                )
            elif order_details["order_type"] == "LIMIT":
                order = self.create_limit_order(
                    order_details["action"],
                    order_details["quantity"],
                    order_details["limit_price"]
                )
            else:
                return {"success": False, "message": f"Unsupported order type: {order_details['order_type']}"}
                
            # Place order
            trade = self.client.ib.placeOrder(contract, order)
            
            # Store order details
            order_id = trade.order.orderId
            self.orders[order_id] = {
                "contract": contract,
                "order": order,
                "trade": trade,
                "status": "SUBMITTED"
            }
            
            logger.info(f"Placed order {order_id}: {order_details['action']} {order_details['quantity']} {order_details['symbol']} {order_details['strike']} {order_details['right']}")
            
            return {"success": True, "order_id": order_id}
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"success": False, "message": str(e)}

    def place_multi_leg_order(self, legs):
        """Place a multi-leg option order"""
        try:
            if not self.client.connected:
                return {"success": False, "message": "Not connected to TWS"}
                
            if not legs or len(legs) == 0:
                return {"success": False, "message": "No order legs provided"}
                
            # For ib_insync, we can create combo contracts for multi-leg orders
            # If all legs are for the same expiry date
            if len(set(leg["expiry"] for leg in legs)) == 1 and len(set(leg["symbol"] for leg in legs)) == 1:
                # Create a bag (combo) contract
                symbol = legs[0]["symbol"]
                combo = Contract()
                combo.symbol = symbol
                combo.secType = "BAG"
                combo.exchange = "SMART"
                combo.currency = "USD"
                
                # Create combo legs
                combo_legs = []
                for leg in legs:
                    # Create and qualify the option contract
                    option_contract = self.create_option_contract(
                        leg["symbol"],
                        leg["expiry"],
                        leg["strike"],
                        leg["right"]
                    )
                    
                    if not option_contract:
                        return {"success": False, "message": f"Failed to create valid contract for leg: {leg['strike']} {leg['right']}"}
                    
                    # Create combo leg
                    combo_leg = ComboLeg()
                    combo_leg.conId = option_contract.conId
                    combo_leg.ratio = int(leg["quantity"])
                    combo_leg.action = leg["action"]
                    combo_leg.exchange = "SMART"
                    
                    combo_legs.append(combo_leg)
                
                combo.comboLegs = combo_legs
                
                # Create the order
                total_quantity = 1  # For combos, this is typically 1
                order = MarketOrder("BUY", total_quantity)
                
                # Place the order
                trade = self.client.ib.placeOrder(combo, order)
                
                # Store order details
                order_id = trade.order.orderId
                self.orders[order_id] = {
                    "contract": combo,
                    "order": order,
                    "trade": trade,
                    "status": "SUBMITTED"
                }
                
                logger.info(f"Placed multi-leg combo order with {len(legs)} legs. Order ID: {order_id}")
                
                return {"success": True, "order_id": order_id}
            else:
                # Handle multiple orders for different expiries or symbols
                # Place them as bracket orders with parent-child relationship
                parent_leg = legs[0]
                
                # Create parent contract
                parent_contract = self.create_option_contract(
                    parent_leg["symbol"],
                    parent_leg["expiry"],
                    parent_leg["strike"],
                    parent_leg["right"]
                )
                
                if not parent_contract:
                    return {"success": False, "message": "Failed to create valid contract for parent leg"}
                
                # Create parent order (not transmitted yet)
                parent_order_type = parent_leg.get("order_type", "MARKET")
                if parent_order_type == "MARKET":
                    parent_order = MarketOrder(
                        parent_leg["action"],
                        parent_leg["quantity"],
                        transmit=False  # Don't transmit yet
                    )
                else:
                    parent_order = LimitOrder(
                        parent_leg["action"],
                        parent_leg["quantity"],
                        parent_leg["limit_price"],
                        transmit=False  # Don't transmit yet
                    )
                
                # Place parent order
                parent_trade = self.client.ib.placeOrder(parent_contract, parent_order)
                parent_id = parent_order.orderId
                
                # Store parent order
                self.orders[parent_id] = {
                    "contract": parent_contract,
                    "order": parent_order,
                    "trade": parent_trade,
                    "status": "SUBMITTED",
                    "children": []
                }
                
                # Place child orders for remaining legs
                child_ids = []
                for i, leg in enumerate(legs[1:], 1):
                    # Create child contract
                    child_contract = self.create_option_contract(
                        leg["symbol"],
                        leg["expiry"],
                        leg["strike"],
                        leg["right"]
                    )
                    
                    if not child_contract:
                        # Cancel parent order since we can't complete the strategy
                        self.client.ib.cancelOrder(parent_order)
                        return {"success": False, "message": f"Failed to create valid contract for leg {i+1}"}
                    
                    # Create child order
                    child_order_type = leg.get("order_type", "MARKET")
                    if child_order_type == "MARKET":
                        child_order = MarketOrder(
                            leg["action"],
                            leg["quantity"],
                            # Last order gets transmitted
                            transmit=(i == len(legs) - 1)
                        )
                    else:
                        child_order = LimitOrder(
                            leg["action"],
                            leg["quantity"],
                            leg["limit_price"],
                            # Last order gets transmitted
                            transmit=(i == len(legs) - 1)
                        )
                    
                    # Link to parent
                    child_order.parentId = parent_id
                    
                    # Place child order
                    child_trade = self.client.ib.placeOrder(child_contract, child_order)
                    child_id = child_order.orderId
                    
                    # Store child order
                    child_ids.append(child_id)
                    self.orders[parent_id]["children"].append(child_id)
                    self.orders[child_id] = {
                        "contract": child_contract,
                        "order": child_order,
                        "trade": child_trade,
                        "status": "SUBMITTED",
                        "parent": parent_id
                    }
                
                logger.info(f"Placed bracket order with {len(legs)} legs. Parent ID: {parent_id}, Child IDs: {child_ids}")
                
                return {"success": True, "order_id": parent_id, "child_ids": child_ids}
                
        except Exception as e:
            logger.error(f"Error placing multi-leg order: {e}")
            return {"success": False, "message": str(e)}

    def cancel_order(self, order_id):
        """Cancel an order by ID"""
        try:
            if not self.client.connected:
                return {"success": False, "message": "Not connected to TWS"}
                
            if order_id not in self.orders:
                return {"success": False, "message": f"Order ID {order_id} not found"}
            
            # Get the order
            order_info = self.orders[order_id]
            
            # Cancel the order
            self.client.ib.cancelOrder(order_info["order"])
            order_info["status"] = "CANCELLING"
            
            logger.info(f"Cancelled order {order_id}")
            
            return {"success": True, "message": f"Order {order_id} cancellation request sent"}
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"success": False, "message": str(e)}

    def get_order_status(self, order_id):
        """Get the status of an order"""
        if not self.client.connected:
            return {"success": False, "message": "Not connected to TWS"}
            
        if order_id not in self.orders:
            return {"success": False, "message": f"Order ID {order_id} not found"}
        
        # Get the latest status from the trade object
        order_info = self.orders[order_id]
        if hasattr(order_info, "trade") and order_info["trade"]:
            status = order_info["trade"].orderStatus.status
            filled = order_info["trade"].orderStatus.filled
            remaining = order_info["trade"].orderStatus.remaining
            
            return {
                "success": True, 
                "status": status,
                "filled": filled,
                "remaining": remaining
            }
        else:
            return {"success": True, "status": order_info["status"]}

# Create order manager instance
order_manager = OrderManager(ibkr_client)