from __future__ import annotations
import threading
import webbrowser
import requests
import random
import time
import os
import sys
import json
import queue
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Any, Optional, Tuple, Dict, Callable

# Add project root to sys.path to allow imports from other directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

# Conditional import for Twisted reactor for GUI integration
_reactor_installed = False
try:
    from twisted.internet import reactor
    _reactor_installed = True
except ImportError:
    print("Twisted reactor not found. GUI integration with Twisted might require manual setup.")

# Imports from ctrader-open-api
try:
    from ctrader_open_api import Client, TcpProtocol, EndPoints, Protobuf
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent, ProtoErrorRes, ProtoMessage
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAApplicationAuthReq, ProtoOAApplicationAuthRes,
        ProtoOAAccountAuthReq, ProtoOAAccountAuthRes,
        ProtoOAGetAccountListByAccessTokenReq, ProtoOAGetAccountListByAccessTokenRes,
        ProtoOATraderReq, ProtoOATraderRes,
        ProtoOASubscribeSpotsReq, ProtoOASubscribeSpotsRes,
        ProtoOASpotEvent, ProtoOATraderUpdatedEvent,
        ProtoOANewOrderReq, ProtoOAExecutionEvent,
        ProtoOAErrorRes,
        ProtoOAGetCtidProfileByTokenRes,
        ProtoOAGetCtidProfileByTokenReq,
        ProtoOASymbolsListReq, ProtoOASymbolsListRes,
        ProtoOASymbolByIdReq, ProtoOASymbolByIdRes,
        ProtoOAGetTrendbarsReq,
        ProtoOAGetTrendbarsRes
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOATrader, ProtoOASymbol,
        ProtoOAOrderType,
        ProtoOATradeSide,
        ProtoOAExecutionType,
        ProtoOAOrderStatus,
        ProtoOATrendbarPeriod
    )
    USE_OPENAPI_LIB = True
except ImportError as e:
    print(f"ctrader-open-api import failed ({e}); running in mock mode.")
    USE_OPENAPI_LIB = False

TOKEN_FILE_PATH = "tokens.json"

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, auth_code_queue: queue.Queue, **kwargs):
        self.auth_code_queue = auth_code_queue
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/callback":
            query_components = urllib.parse.parse_qs(parsed_path.query)
            auth_code = query_components.get("code", [None])[0]

            if auth_code:
                self.auth_code_queue.put(auth_code)
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Authentication Successful!</h1>")
                self.wfile.write(b"<p>You can close this browser tab and return to the application.</p></body></html>")
                print(f"OAuth callback handled, code extracted: {auth_code[:20]}...")
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Authentication Failed</h1><p>No authorization code found in callback.</p></body></html>")
                print("OAuth callback error: No authorization code found.")
                self.auth_code_queue.put(None)
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Not Found</h1></body></html>")

    def log_message(self, format, *args):
        if "400" in args[0] or "404" in args[0] or "code 200" in args[0]:
             super().log_message(format, *args)

class CTraderClient:
    def __init__(self, on_account_update: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.on_account_update = on_account_update
        self.is_connected: bool = False
        self._is_client_connected: bool = False
        self._last_error: str = ""
        self.price_history: Dict[str, List[float]] = {}
        self.history_size = 100

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._load_tokens_from_file()

        self.ctid_trader_account_id: Optional[int] = int(Config.CTRADING_ACCOUNT_ID) if Config.CTRADING_ACCOUNT_ID else None
        self.account_id: Optional[str] = None
        self.balance: Optional[float] = None
        self.equity: Optional[float] = None
        self.currency: Optional[str] = None
        self.used_margin: Optional[float] = None

        self.symbols_map: Dict[str, int] = {}
        self.symbol_details_map: Dict[int, Any] = {}
        self.subscribed_spot_symbol_ids: set[int] = set()

        self._client: Optional[Client] = None
        self._message_id_counter: int = 1
        self._reactor_thread: Optional[threading.Thread] = None
        self._auth_code: Optional[str] = None
        self._account_auth_initiated: bool = False

        if USE_OPENAPI_LIB:
            host = (
                EndPoints.PROTOBUF_LIVE_HOST
                if Config.CTRADER_HOST_TYPE == "live"
                else EndPoints.PROTOBUF_DEMO_HOST
            )
            port = EndPoints.PROTOBUF_PORT
            self._client = Client(host, port, TcpProtocol)
            self._client.setConnectedCallback(self._on_client_connected)
            self._client.setDisconnectedCallback(self._on_client_disconnected)
            self._client.setMessageReceivedCallback(self._on_message_received)
        else:
            print("Trader initialized in MOCK mode.")

        self._auth_code_queue = queue.Queue()
        self._http_server_thread: Optional[threading.Thread] = None
        self._http_server: Optional[HTTPServer] = None

    def _save_tokens_to_file(self):
        tokens = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "token_expires_at": self._token_expires_at,
        }
        try:
            with open(TOKEN_FILE_PATH, "w") as f:
                json.dump(tokens, f)
            print(f"Tokens saved to {TOKEN_FILE_PATH}")
        except IOError as e:
            print(f"Error saving tokens to {TOKEN_FILE_PATH}: {e}")

    def _load_tokens_from_file(self):
        try:
            with open(TOKEN_FILE_PATH, "r") as f:
                tokens = json.load(f)
            self._access_token = tokens.get("access_token")
            self._refresh_token = tokens.get("refresh_token")
            self._token_expires_at = tokens.get("token_expires_at")
            if self._access_token:
                print(f"Tokens loaded from {TOKEN_FILE_PATH}. Access token: {self._access_token[:20]}...")
            else:
                print(f"{TOKEN_FILE_PATH} not found or no access token in it. Will need OAuth.")
        except FileNotFoundError:
            print(f"Token file {TOKEN_FILE_PATH} not found. New OAuth flow will be required.")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading tokens from {TOKEN_FILE_PATH}: {e}.")
            try:
                os.remove(TOKEN_FILE_PATH)
                print(f"Removed corrupted token file: {TOKEN_FILE_PATH}")
            except OSError as rm_err:
                print(f"Error removing corrupted token file: {rm_err}")

    def _next_message_id(self) -> str:
        mid = str(self._message_id_counter)
        self._message_id_counter += 1
        return mid

    def _on_client_connected(self, client: Client) -> None:
        print("OpenAPI Client Connected.")
        self._is_client_connected = True
        self._last_error = ""
        req = ProtoOAApplicationAuthReq()
        req.clientId = Config.CTRADING_CLIENT_ID
        req.clientSecret = Config.CTRADING_CLIENT_SECRET
        if not req.clientId or not req.clientSecret:
            print("Missing OpenAPI credentials.")
            client.stopService()
            return
        print(f"Sending ProtoOAApplicationAuthReq")
        d = client.send(req)
        d.addCallbacks(self._handle_app_auth_response, self._handle_send_error)

    def _on_client_disconnected(self, client: Client, reason: Any) -> None:
        print(f"OpenAPI Client Disconnected: {reason}")
        self.is_connected = False
        self._is_client_connected = False
        self._account_auth_initiated = False

    def _on_message_received(self, client: Client, message: Any) -> None:
        try:
            actual_message = Protobuf.extract(message)
        except Exception as e:
            print(f"Error using Protobuf.extract: {e}. Falling back to manual deserialization if possible.")
            actual_message = message

        if isinstance(actual_message, ProtoOAApplicationAuthRes):
            self._handle_app_auth_response(actual_message)
        elif isinstance(actual_message, ProtoOAAccountAuthRes):
            self._handle_account_auth_response(actual_message)
        elif isinstance(actual_message, ProtoOAGetAccountListByAccessTokenRes):
            self._handle_get_account_list_response(actual_message)
        elif isinstance(actual_message, ProtoOASymbolsListRes):
            self._handle_symbols_list_response(actual_message)
        elif isinstance(actual_message, ProtoOASymbolByIdRes):
            self._handle_symbol_details_response(actual_message)
        elif isinstance(actual_message, ProtoOATraderRes):
            self._handle_trader_response(actual_message)
        elif isinstance(actual_message, ProtoOATraderUpdatedEvent):
            self._handle_trader_updated_event(actual_message)
        elif isinstance(actual_message, ProtoOASpotEvent):
            self._handle_spot_event(actual_message)
        elif isinstance(actual_message, ProtoOAExecutionEvent):
            self._handle_execution_event(actual_message)
        elif isinstance(actual_message, ProtoOAGetTrendbarsRes):
            self._handle_get_trendbars_response(actual_message)
        elif isinstance(actual_message, ProtoHeartbeatEvent):
            pass
        elif isinstance(actual_message, (ProtoOAErrorRes, ProtoErrorRes)):
            self._last_error = f"{actual_message.errorCode}: {actual_message.description}"
            print(self._last_error)
            if "NOT_AUTHENTICATED" in actual_message.errorCode:
                self.disconnect()
        else:
            if isinstance(actual_message, ProtoMessage):
                print(f"Unhandled ProtoMessage with PayloadType {actual_message.payloadType}")
            else:
                print(f"Unhandled message type in _on_message_received: {type(actual_message)}")


    def _handle_app_auth_response(self, response: ProtoOAApplicationAuthRes) -> None:
        print("Application authenticated.")
        if self._account_auth_initiated:
            return

        if not self._access_token:
            self._last_error = "Critical: OAuth access token not available for subsequent account operations."
            print(self._last_error)
            if self._client:
                self._client.stopService()
            return

        if self.ctid_trader_account_id and self._access_token:
            self._account_auth_initiated = True
            self._send_account_auth_request(self.ctid_trader_account_id)
        elif self._access_token:
            self._account_auth_initiated = True
            self._send_get_account_list_request()
        else:
            self._last_error = "Critical: Cannot proceed with account auth/discovery. Missing ctidTraderAccountId or access token after app auth."
            print(self._last_error)
            if self._client:
                self._client.stopService()

    def _handle_account_auth_response(self, response: ProtoOAAccountAuthRes) -> None:
        if response.ctidTraderAccountId == self.ctid_trader_account_id:
            print(f"Successfully authenticated account {self.ctid_trader_account_id}.")
            self.is_connected = True
            self._last_error = ""
            self._send_get_trader_request(self.ctid_trader_account_id)
            self._send_get_symbols_list_request()
        else:
            self._last_error = "Account authentication failed (ID mismatch or error)."
            self.is_connected = False
            if self._client:
                self._client.stopService()

    def _handle_get_account_list_response(self, response: ProtoOAGetAccountListByAccessTokenRes) -> None:
        accounts = getattr(response, 'ctidTraderAccount', [])
        if not accounts:
            self._last_error = "No trading accounts found for this access token."
            if self._client and self._is_client_connected:
                self._client.stopService()
            return

        selected_account = accounts[0]
        if not selected_account.ctidTraderAccountId:
            self._last_error = "Account found but missing ID."
            return

        self.ctid_trader_account_id = selected_account.ctidTraderAccountId
        print(f"Selected ctidTraderAccountId from list: {self.ctid_trader_account_id}")
        self._send_account_auth_request(self.ctid_trader_account_id)

    def _handle_symbols_list_response(self, response: ProtoOASymbolsListRes):
        self.symbols_map.clear()
        for light_symbol_proto in response.symbol:
            self.symbols_map[light_symbol_proto.symbolName] = light_symbol_proto.symbolId
        print(f"Loaded {len(self.symbols_map)} symbols.")
        # You might want to subscribe to a default symbol here
        # For example, find "EURUSD" and subscribe
        if "EURUSD" in self.symbols_map:
            self._send_subscribe_spots_request(self.ctid_trader_account_id, [self.symbols_map["EURUSD"]])


    def _handle_symbol_details_response(self, response: ProtoOASymbolByIdRes):
        for detailed_symbol_proto in response.symbol:
            self.symbol_details_map[detailed_symbol_proto.symbolId] = detailed_symbol_proto
        print(f"Loaded details for {len(response.symbol)} symbols.")

    def _handle_trader_response(self, response: ProtoOATraderRes):
        self._update_trader_details("Trader details response.", response.trader)

    def _handle_trader_updated_event(self, event: ProtoOATraderUpdatedEvent):
        self._update_trader_details("Trader updated event.", event.trader)

    def _update_trader_details(self, log_message: str, trader_proto: ProtoOATrader):
        if trader_proto:
            self.account_id = str(trader_proto.ctidTraderAccountId)
            self.balance = trader_proto.balance / 100.0
            self.equity = trader_proto.equity / 100.0
            if self.on_account_update:
                self.on_account_update(self.get_account_summary())

    def _handle_spot_event(self, event: ProtoOASpotEvent):
        symbol_id = event.symbolId
        symbol_name = next((name for name, s_id in self.symbols_map.items() if s_id == symbol_id), None)
        if not symbol_name:
            return

        if symbol_name not in self.price_history:
            self.price_history[symbol_name] = []

        if hasattr(event, 'bid') and event.bid is not None:
            digits = self.symbol_details_map.get(symbol_id, {}).get('digits', 5)
            price = event.bid / (10**digits)
            self.price_history[symbol_name].append(price)
            if len(self.price_history[symbol_name]) > self.history_size:
                self.price_history[symbol_name].pop(0)

    def _handle_execution_event(self, event: ProtoOAExecutionEvent):
        print(f"Execution Event: {event}")

    def _handle_get_trendbars_response(self, response: ProtoOAGetTrendbarsRes):
        print(f"Received {len(response.trendbar)} trendbars for symbol {response.symbolId}")

    def _handle_send_error(self, failure: Any) -> None:
        print(f"Send error: {failure.getErrorMessage()}")
        self._last_error = failure.getErrorMessage()

    def connect(self) -> bool:
        if not USE_OPENAPI_LIB:
            self._last_error = "OpenAPI library not available (mock mode)."
            return False

        if self._access_token and not self._is_token_expired():
            print("Using previously saved, valid access token.")
            return self._start_openapi_client_service()

        if self._refresh_token:
            if self.refresh_access_token():
                print("Access token refreshed successfully.")
                return self._start_openapi_client_service()
            else:
                print("Failed to refresh token. Proceeding to full OAuth flow.")

        print("Initiating full OAuth2 flow...")
        auth_url = Config.CTRADER_SPOTWARE_AUTH_URL
        client_id = Config.CTRADING_CLIENT_ID
        redirect_uri = Config.CTRADER_REDIRECT_URI
        scopes = "trading"
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes
        }
        auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(params)}"

        if not self._start_local_http_server():
            self._last_error = "OAuth2 Error: Could not start local HTTP server for callback."
            return False

        webbrowser.open(auth_url_with_params)
        self._last_error = "OAuth2: Waiting for authorization code..."

        try:
            auth_code = self._auth_code_queue.get(timeout=120)
        except queue.Empty:
            self._last_error = "OAuth2 Error: Timeout waiting for callback."
            self._stop_local_http_server()
            return False

        self._stop_local_http_server()

        if auth_code:
            return self.exchange_code_for_token(auth_code)
        else:
            self._last_error = "OAuth2 Error: Invalid authorization code received."
            return False

    def _start_local_http_server(self) -> bool:
        try:
            if self._http_server_thread and self._http_server_thread.is_alive():
                self._stop_local_http_server()

            parsed_uri = urllib.parse.urlparse(Config.CTRADER_REDIRECT_URI)
            host = parsed_uri.hostname
            port = parsed_uri.port

            if not host or not port:
                return False

            def handler_factory(*args, **kwargs):
                return OAuthCallbackHandler(*args, auth_code_queue=self._auth_code_queue, **kwargs)

            self._http_server = HTTPServer((host, port), handler_factory)
            self._http_server_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_server_thread.start()
            return True
        except Exception as e:
            self._last_error = f"Failed to start local HTTP server: {e}"
            return False

    def _stop_local_http_server(self):
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None
        if self._http_server_thread and self._http_server_thread.is_alive():
            self._http_server_thread.join(timeout=5)
        self._http_server_thread = None

    def exchange_code_for_token(self, auth_code: str) -> bool:
        try:
            payload = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": Config.CTRADER_REDIRECT_URI,
                "client_id": Config.CTRADING_CLIENT_ID,
                "client_secret": Config.CTRADING_CLIENT_SECRET,
            }
            response = requests.post(Config.CTRADER_SPOTWARE_TOKEN_URL, data=payload)
            response.raise_for_status()
            token_data = response.json()

            if "access_token" not in token_data:
                self._last_error = "OAuth2 Error: access_token not in response."
                return False

            self._access_token = token_data["access_token"]
            self._refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            if expires_in:
                self._token_expires_at = time.time() + int(expires_in)

            self._save_tokens_to_file()
            return self._start_openapi_client_service()

        except requests.exceptions.RequestException as e:
            self._last_error = f"OAuth2 Request Error: {e}"
            return False

    def _start_openapi_client_service(self):
        if self.is_connected or (self._client and getattr(self._client, 'isConnected', False)):
            return True

        try:
            self._client.startService()
            if _reactor_installed and not reactor.running:
                self._reactor_thread = threading.Thread(target=lambda: reactor.run(installSignalHandlers=0), daemon=True)
                self._reactor_thread.start()
            return True
        except Exception as e:
            self._last_error = f"OpenAPI client error: {e}"
            return False

    def refresh_access_token(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": Config.CTRADING_CLIENT_ID,
                "client_secret": Config.CTRADING_CLIENT_SECRET,
            }
            response = requests.post(Config.CTRADER_SPOTWARE_TOKEN_URL, data=payload)
            response.raise_for_status()
            token_data = response.json()

            if "access_token" not in token_data:
                return False

            self._access_token = token_data["access_token"]
            if "refresh_token" in token_data:
                self._refresh_token = token_data["refresh_token"]
            expires_in = token_data.get("expires_in")
            if expires_in:
                self._token_expires_at = time.time() + int(expires_in)

            self._save_tokens_to_file()
            return True
        except requests.exceptions.RequestException:
            return False

    def _is_token_expired(self, buffer_seconds: int = 60) -> bool:
        if not self._access_token or not self._token_expires_at:
            return True
        return time.time() > (self._token_expires_at - buffer_seconds)

    def disconnect(self) -> None:
        if self._client:
            self._client.stopService()
        if _reactor_installed and reactor.running:
            reactor.callFromThread(reactor.stop)
        self.is_connected = False
        self._is_client_connected = False

    def get_connection_status(self) -> Tuple[bool, str]:
        return self.is_connected, self._last_error

    def get_account_summary(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.used_margin
        }

    def _send_account_auth_request(self, ctid: int) -> None:
        if not self._ensure_valid_token():
            return
        req = ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = ctid
        req.accessToken = self._access_token or ""
        self._client.send(req)

    def _send_get_account_list_request(self) -> None:
        if not self._ensure_valid_token():
            return
        req = ProtoOAGetAccountListByAccessTokenReq()
        req.accessToken = self._access_token
        self._client.send(req)

    def _send_get_trader_request(self, ctid: int) -> None:
        if not self._ensure_valid_token():
            return
        req = ProtoOATraderReq()
        req.ctidTraderAccountId = ctid
        self._client.send(req)

    def _send_get_symbols_list_request(self) -> None:
        if not self._ensure_valid_token():
            return
        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = self.ctid_trader_account_id
        self._client.send(req)

    def _send_subscribe_spots_request(self, ctid_trader_account_id: int, symbol_ids: List[int]) -> None:
        if not self._ensure_valid_token():
            return
        req = ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = ctid_trader_account_id
        req.symbolId.extend(symbol_ids)
        self._client.send(req)

    def _ensure_valid_token(self) -> bool:
        if self._is_token_expired():
            if not self.refresh_access_token():
                if self._client and self._is_client_connected:
                    self._client.stopService()
                self.is_connected = False
                return False
        return True

    def get_positions(self):
        if not self.is_connected:
            print("Not connected to cTrader")
            return None
        request = ProtoOAGetPositionListReq()
        request.ctidTraderAccountId = self.ctid_trader_account_id
        return self._client.send(request)

    def submit_order(self, order_data):
        if not self.is_connected:
            print("Not connected to cTrader")
            return

        symbol_name = order_data.get("symbol")
        side = order_data.get("side")
        qty_lots = order_data.get("qty")

        if not all([symbol_name, side, qty_lots]):
            print("Order data is missing required fields.")
            return

        symbol_id = self.symbols_map.get(symbol_name)
        if not symbol_id:
            print(f"Symbol '{symbol_name}' not found.")
            return

        symbol_details = self.symbol_details_map.get(symbol_id)
        if not symbol_details:
            print(f"Details for symbol '{symbol_name}' not loaded.")
            return

        volume_in_units = int(qty_lots * symbol_details.lotSize)

        request = ProtoOANewOrderReq()
        request.ctidTraderAccountId = self.ctid_trader_account_id
        request.symbolId = symbol_id
        request.orderType = ProtoOAOrderType.MARKET
        request.tradeSide = ProtoOATradeSide.BUY if side.upper() == "BUY" else ProtoOATradeSide.SELL
        request.volume = volume_in_units

        print(f"Submitting order: {request}")
        self._client.send(request)

    def get_tradable_symbols(self):
        if not self.is_connected:
            print("Not connected to cTrader")
            return None
        return list(self.symbols_map.keys())

    def get_bars(self, symbol, is_crypto=False):
        if not self.is_connected:
            print("Not connected to cTrader")
            return None

        symbol_id = self.symbols_map.get(symbol)
        if not symbol_id:
            print(f"Symbol '{symbol}' not found.")
            return None

        request = ProtoOAGetTrendbarsReq()
        request.ctidTraderAccountId = self.ctid_trader_account_id
        request.symbolId = symbol_id
        request.period = ProtoOATrendbarPeriod.M1
        request.count = 100

        return self._client.send(request)

    def check_connection(self):
        return self.is_connected

    def close(self):
        self.disconnect()

if __name__ == '__main__':
    # Example usage (for testing)
    client_id = input("Enter your cTrader Client ID: ")
    client_secret = input("Enter your cTrader Client Secret: ")
    account_id = input("Enter your cTrader Account ID: ")
    Config.update_credentials(client_id, client_secret, account_id)

    def on_account_update(summary):
        print(f"Account Summary Update: {summary}")

    client = CTraderClient(on_account_update=on_account_update)

    if client.connect():
        print("Connection process initiated. Please check your web browser to authenticate.")

        # In a real application, you would have a more sophisticated way of waiting
        # for the connection to be fully established. For this test, we will
        # simply start the reactor and periodically check the connection status.

        def check_status():
            connected, error_msg = client.get_connection_status()
            if connected:
                print("Successfully connected to cTrader!")
                # Once connected, you could perform some test actions, e.g.,
                # print("Fetching positions...")
                # client.get_positions().addCallback(print)
            elif error_msg:
                print(f"Connection failed: {error_msg}")
                if reactor.running:
                    reactor.stop()

        if _reactor_installed:
            # Check status shortly after starting, to allow time for connection
            reactor.callLater(5, check_status)
            print("Starting Twisted reactor. Press Ctrl+C to stop.")
            reactor.run()
    else:
        print(f"Failed to initiate connection: {client.get_connection_status()[1]}")
