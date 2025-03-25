import socket
import select
import sys
from _thread import *

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

if len(sys.argv) != 3:
    print("Correct usage: script, IP address, port number")
    exit()

IP_address = str(sys.argv[1])
Port = int(sys.argv[2])

server.bind((IP_address, Port))
server.listen(100)

list_of_clients = []

def clientthread(conn, addr):
    """ Function to handle client messages """
    conn.send("Welcome to this chatroom!".encode())

    while True:
        try:
            message = conn.recv(2048).decode()
            if message:
                print(f"<{addr[0]}> {message}")  # Show client message on server
                message_to_send = f"<{addr[0]}> {message}".encode()
                broadcast(message_to_send, conn)
            else:
                remove(conn)
        except:
            continue

def broadcast(message, connection=None):
    """ Send messages to all clients. """
    for client in list_of_clients:
        if connection is None or client != connection:
            try:
                client.send(message)
            except:
                client.close()
                remove(client)

def remove(connection):
    """ Remove a client from the list """
    if connection in list_of_clients:
        list_of_clients.remove(connection)

def server_input():
    """ Allow server to send messages manually """
    while True:
        message = input()  # Server admin types a message
        message_to_send = f"<Server> {message}".encode()
        broadcast(message_to_send)  # Send to all clients
        print(f"<Server> {message}")  # Show on server console

# Start server input thread (so server can type messages)
start_new_thread(server_input, ())

while True:
    conn, addr = server.accept()
    list_of_clients.append(conn)
    print(f"{addr[0]} connected")
    start_new_thread(clientthread, (conn, addr))

conn.close()
server.close()
