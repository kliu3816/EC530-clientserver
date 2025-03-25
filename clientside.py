import socket
import select
import sys
import threading

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

if len(sys.argv) != 3:
    print("Correct usage: script, IP address, port number")
    exit()

IP_address = str(sys.argv[1])
Port = int(sys.argv[2])
server.connect((IP_address, Port))

def send_messages():
    """ Function to continuously read user input and send it to the server """
    while True:
        message = input()  # Use input() instead of sys.stdin.readline()
        server.send(message.encode())  # Encode message before sending
        print(f"<You> {message}")

# Start a new thread for handling user input
threading.Thread(target=send_messages, daemon=True).start()

while True:
    # Only check for incoming messages
    read_sockets, _, _ = select.select([server], [], [])

    for socks in read_sockets:
        message = socks.recv(2048).decode()
        if message:
            print(message)
        else:
            print("Disconnected from server.")
            server.close()
            sys.exit()
