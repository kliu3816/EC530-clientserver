import socket
import threading
import sqlite3
import datetime
import sys
import json

DB_NAME = "chat.db"

# --- Database Functions ---
def create_db():
    """Creates the messages table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            username TEXT,
            direction TEXT,   -- "sent" or "received"
            message TEXT,
            status TEXT       -- e.g., "delivered", "pending"
        )
    ''')
    conn.commit()
    conn.close()

def log_message(username, direction, message, status="delivered"):
    """Logs a message to the database with a UTC timestamp."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()  # UTC timestamp
    cursor.execute('''
        INSERT INTO messages (timestamp, username, direction, message, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (timestamp, username, direction, message, status))
    conn.commit()
    conn.close()

def get_all_messages():
    """Retrieve all messages from the database, ordered by timestamp."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, username, direction, message FROM messages
        ORDER BY timestamp ASC
    ''')
    messages = cursor.fetchall()
    conn.close()
    return messages

def get_messages_since(last_timestamp):
    """Retrieve messages from the database after the given timestamp."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, username, direction, message FROM messages
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    ''', (last_timestamp,))
    messages = cursor.fetchall()
    conn.close()
    return messages

def format_time(ts):
    """Converts a full ISO timestamp to only display hour and minute."""
    try:
        dt = datetime.datetime.fromisoformat(ts)
        return dt.strftime("%H:%M")
    except Exception:
        return ts
    
def load_history():
    """Loads and prints the chat history from the database with time in HH:MM format."""
    messages = get_all_messages()
    if messages:
        print("\n--- Chat History ---")
        for ts, user, direction, message in messages:
            time_formatted = format_time(ts)
            print(f"[{time_formatted}] <{user}> {message}")
        print("--- End of History ---\n")
    else:
        print("\nNo previous chat history found.\n")

# --- Peer-to-Peer Chat Functions ---
class Peer:
    def __init__(self, username, listen_ip, listen_port, peer_ip=None, peer_port=None):
        self.username = username
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.connections = []  # list to store connected sockets
        self.last_received_timestamp = "1970-01-01T00:00:00"  # default starting point

        # Create or update the database
        create_db()
        # Load chat history
        load_history()

        # Start a thread for listening (server functionality)
        listener = threading.Thread(target=self.listen_for_peers, daemon=True)
        listener.start()

        # If a peer IP/port is provided, connect to that peer
        if self.peer_ip and self.peer_port:
            self.connect_to_peer(self.peer_ip, self.peer_port)

        # Start the user input thread for sending messages
        sender = threading.Thread(target=self.send_messages, daemon=True)
        sender.start()

    def listen_for_peers(self):
        """Listens for incoming peer connections."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.listen_ip, self.listen_port))
        server.listen(5)
        print(f"[Listening on {self.listen_ip}:{self.listen_port}]")
        while True:
            conn, addr = server.accept()
            self.connections.append(conn)
            print(f"[Connected by {addr}]")
            # Start a thread to handle this connection
            threading.Thread(target=self.handle_peer, args=(conn, addr), daemon=True).start()

    def connect_to_peer(self, peer_ip, peer_port):
        """Connects to another peer and requests missed messages."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((peer_ip, peer_port))
            self.connections.append(client)
            print(f"[Connected to peer at {peer_ip}:{peer_port}]")
            # Start a thread to listen for messages from this peer
            threading.Thread(target=self.handle_peer, args=(client, (peer_ip, peer_port)), daemon=True).start()
            # After connecting, send last received timestamp to request missed messages
            request = {"type": "sync_request", "last_timestamp": self.last_received_timestamp}
            client.send(json.dumps(request).encode())
        except Exception as e:
            print(f"Error connecting to peer: {e}")

    def handle_peer(self, conn, addr):
        """Handles communication with a connected peer."""
        while True:
            try:
                data = conn.recv(2048)
                if not data:
                    print(f"[{addr} disconnected]")
                    if conn in self.connections:
                        self.connections.remove(conn)
                    conn.close()
                    break
                try:
                    # Try to decode JSON data
                    message_obj = json.loads(data.decode())
                    if message_obj.get("type") == "sync_request":
                        # Peer is requesting messages since a given timestamp
                        last_ts = message_obj.get("last_timestamp", "1970-01-01T00:00:00")
                        missing = get_messages_since(last_ts)
                        # Send the missing messages as a JSON list
                        response = {"type": "sync_response", "messages": missing}
                        conn.send(json.dumps(response).encode())
                    elif message_obj.get("type") == "sync_response":
                        # We have received missing messages from the peer
                        messages = message_obj.get("messages", [])
                        for msg in messages:
                            # Log and print each missing message
                            log_message(username=msg[1], direction=msg[2], message=msg[3])
                            print(f"[Missed] <{msg[1]}> {msg[3]}")
                            # Update last_received_timestamp if newer
                            if msg[0] > self.last_received_timestamp:
                                self.last_received_timestamp = msg[0]
                    else:
                        # Assume it's a normal chat message
                        message = message_obj.get("message", "")
                        log_message(username=self.username, direction="received", message=message)
                        print(f"<{addr}> {message}")
                        # Update last_received_timestamp
                        ts = datetime.datetime.now(datetime.UTC).isoformat()
                        self.last_received_timestamp = ts
                except json.JSONDecodeError:
                    # If not JSON, assume it's a plain message
                    message = data.decode()
                    log_message(username=self.username, direction="received", message=message)
                    print(f"<{addr}> {message}")
                    ts = datetime.datetime.now(datetime.UTC).isoformat()
                    self.last_received_timestamp = ts
            except Exception as e:
                print(f"Error handling peer {addr}: {e}")
                if conn in self.connections:
                    self.connections.remove(conn)
                conn.close()
                break

    def send_messages(self):
        """Reads user input and sends messages to all connected peers."""
        while True:
            message = input()  # User input
            # Log the sent message
            log_message(username=self.username, direction="sent", message=message)
            # Wrap the message in JSON so that it can be handled uniformly
            message_obj = {"type": "chat", "message": message}
            for conn in list(self.connections):
                try:
                    conn.send(json.dumps(message_obj).encode())
                except Exception as e:
                    print(f"Error sending message: {e}")
                    if conn in self.connections:
                        self.connections.remove(conn)
                    conn.close()
            print(f"<You> {message}")

if __name__ == "__main__":
    # Example usage:
    # Run as: python peer_chat.py <username> <listen_ip> <listen_port> [peer_ip] [peer_port]
    # If peer_ip and peer_port are provided, this peer will attempt to connect to that peer.
    if len(sys.argv) < 4:
        print("Usage: python peer_chat.py <username> <listen_ip> <listen_port> [peer_ip] [peer_port]")
        sys.exit()

    username = sys.argv[1]
    listen_ip = sys.argv[2]
    listen_port = int(sys.argv[3])

    peer_ip = None
    peer_port = None
    if len(sys.argv) == 6:
        peer_ip = sys.argv[4]
        peer_port = int(sys.argv[5])

    # Initialize the peer (this will load and display history)
    Peer(username, listen_ip, listen_port, peer_ip, peer_port)

    # Keep the main thread alive.
    while True:
        pass
