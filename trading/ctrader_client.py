# trading/ctrader_client.py

import os
import sys
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

class CTraderClient:
    def __init__(self):
        self.client_id = Config.CTRADING_CLIENT_ID
        self.client_secret = Config.CTRADING_CLIENT_SECRET
        self.account_id = Config.CTRADING_ACCOUNT_ID
        self.host = EndPoints.PROTOBUF_LIVE_HOST  # or EndPoints.PROTOBUF_DEMO_HOST
        self.port = EndPoints.PROTOBUF_PORT
        self.client = None

    def connect(self):
        self.d = Deferred()
        self.client = Client(self.host, self.port, TcpProtocol)

        # Set up callbacks
        self.client.setConnectedCallback(self.on_connected)
        self.client.setDisconnectedCallback(self.on_disconnected)
        self.client.setMessageReceivedCallback(self.on_message_received)

        # The client starts connecting automatically upon instantiation
        return self.d

    def on_connected(self, client):
        print("Connected to cTrader")
        # Authenticate the application
        request = ProtoOAApplicationAuthReq()
        request.clientId = self.client_id
        request.clientSecret = self.client_secret
        self.client.send(request).addCallback(self.on_auth_response)

    def on_auth_response(self, response):
        if response.payloadType == ProtoOAPayloadType.PROTO_OA_APPLICATION_AUTH_RES:
            self.d.callback(self.client)

    def on_disconnected(self, client, reason):
        print(f"Disconnected from cTrader: {reason}")

    def on_message_received(self, client, message):
        print(f"Message received: {Protobuf.extract(message)}")

    def get_account(self):
        if not self.client or not self.client.is_connected():
            print("Not connected to cTrader")
            return None

        request = ProtoOAGetAccountListReq()
        request.accessToken = "YOUR_ACCESS_TOKEN"  # This needs to be obtained from the OAuth flow
        deferred = self.client.send(request)
        return deferred

    def get_positions(self):
        if not self.client or not self.client.is_connected():
            print("Not connected to cTrader")
            return None

        request = ProtoOAGetPositionListReq()
        request.accessToken = "YOUR_ACCESS_TOKEN"
        request.ctidTraderAccountId = int(self.account_id)
        deferred = self.client.send(request)
        return deferred

    def submit_order(self, order_data):
        if not self.client or not self.client.is_connected():
            print("Not connected to cTrader")
            return None

        request = ProtoOANewOrderReq()
        request.accessToken = "YOUR_ACCESS_TOKEN"
        request.ctidTraderAccountId = int(self.account_id)
        request.symbolName = order_data["symbol"]
        request.orderType = ProtoOAOrderType.MARKET
        request.tradeSide = ProtoOATradeSide.BUY if order_data["side"] == "BUY" else ProtoOATradeSide.SELL
        request.volume = int(order_data["qty"] * 100)  # cTrader uses cents

        deferred = self.client.send(request)
        return deferred

    def get_tradable_symbols(self):
        if not self.client or not self.client.is_connected():
            print("Not connected to cTrader")
            return None

        request = ProtoOAGetSymbolsListReq()
        request.accessToken = "YOUR_ACCESS_TOKEN"
        request.ctidTraderAccountId = int(self.account_id)

        deferred = self.client.send(request)
        return deferred

    def cancel_all_orders(self):
        # This will be implemented later
        pass

    def get_bars(self, symbol, is_crypto=False):
        if not self.client or not self.client.is_connected():
            print("Not connected to cTrader")
            return None

        request = ProtoOAGetTrendbarsReq()
        request.accessToken = "YOUR_ACCESS_TOKEN"
        request.ctidTraderAccountId = int(self.account_id)
        request.symbolName = symbol
        request.period = ProtoOATrendbarPeriod.M1
        request.count = 100

        deferred = self.client.send(request)
        return deferred

    def check_connection(self):
        return self.client and self.client.is_connected()

    def close(self):
        if self.client and self.client.is_connected():
            self.client.stop()

if __name__ == '__main__':
    # Example usage (for testing)
    client = CTraderClient()
    client.connect()
    # To run the reactor
    # reactor.run()
