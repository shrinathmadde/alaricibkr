# test_ibkr.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import time

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        
    def error(self, reqId, errorCode, errorString):
        print(f"Error: {reqId} {errorCode} {errorString}")
        
    def nextValidId(self, orderId):
        print(f"Connected to TWS. Next valid order ID: {orderId}")
        self.disconnect()

app = TestApp()
app.connect("127.0.0.1", 7496, 0)  # Use 7496 for live trading
print("Connecting to TWS...")
app.run()