import threading
from socket import *
from threading import *
from uu import encode  # Note: 'uu.encode' is imported but not used in the code.

import select  # Imported for handling multiple socket connections in UDP Server.


# -------------------- TCP Server Implementation -------------------- #
class ServerTCP:
    def __init__(self, server_port):
        """
        Initialize the TCP server with the specified port.
        Sets up the server socket and initializes necessary variables.
        """
        self.server_port = server_port
        self.server_socket = socket(AF_INET, SOCK_STREAM)  # Create a TCP socket.
        self.clients = {}  # Dictionary to store client sockets and their corresponding names.
        self.run_event = threading.Event()  # Event to control the server's running state.
        self.handle_event = threading.Event()  # Event to control client handling.
        self.server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # Allow reuse of local addresses.
        self.server_socket.bind(('localhost', self.server_port))  # Bind the socket to localhost and the specified port.
        self.server_socket.settimeout(2)  # Set a timeout for blocking socket operations.
        self.server_socket.listen(5)  # Listen for incoming connections with a backlog of 5.

    def accept_client(self):
        """
        Accept a new client connection.
        Receives the client's name and checks for uniqueness.
        Sends a welcome message or rejection if the name is taken.
        """
        try:
            client_socket, addr = self.server_socket.accept()  # Accept a new connection.
            message = client_socket.recv(4096).decode()  # Receive the client's name.

            if message in self.clients.values():
                client_socket.send("Name already taken".encode())  # Inform the client that the name is taken.
                print("Name already taken")
                return False  # Indicate that the client was not accepted.

            client_socket.send(("Welcome " + message).encode())  # Send a welcome message to the client.
            print("Welcome " + message)
            self.clients[client_socket] = message  # Add the client to the clients dictionary.
            self.broadcast(client_socket, "join")  # Notify other clients about the new user.
            return True  # Indicate that the client was successfully accepted.
        except timeout:
            return False  # No client connected within the timeout period.

    def close_client(self, client_socket):
        """
        Remove a client from the clients dictionary.
        """
        if client_socket in self.clients:
            self.clients.pop(client_socket)  # Remove the client from the dictionary.
            return True  # Indicate that the client was successfully removed.
        return False  # Indicate that the client was not found.

    def broadcast(self, client_socket_sent, message):
        """
        Broadcast a message to all clients except the sender.
        Handles different types of messages: join, exit, or regular messages.
        """
        if 'join' == message:
            # Notify others that a user has joined.
            self.send_broadcast_message(
                client_socket_sent,
                message,
                f"User {self.clients.get(client_socket_sent)} has joined"
            )
        elif 'exit' == message:
            # Notify others that a user has left.
            self.send_broadcast_message(
                client_socket_sent,
                message,
                f"User {self.clients.get(client_socket_sent)} has left"
            )
        elif message == '':
            # Ignore empty messages.
            return
        else:
            # Broadcast regular messages.
            self.send_broadcast_message(client_socket_sent, "", message)

    def send_broadcast_message(self, client_socket_sent, message, broadcast_message):
        """
        Send a formatted broadcast message to all clients except the sender.
        """
        for key in self.clients:
            if key != client_socket_sent:
                if message == 'join' or message == 'exit':
                    # Send join or exit notifications as-is.
                    key.send(broadcast_message.encode())
                else:
                    # Prefix regular messages with the sender's name.
                    key.send(f"{self.clients.get(client_socket_sent)}: {broadcast_message}".encode())

    def shutdown(self):
        """
        Shutdown the server gracefully.
        Sends a shutdown message to all clients and closes all sockets.
        """
        print("Shutting down server...")
        for key in self.clients:
            key.send("server-shutdown".encode())  # Notify clients about shutdown.
            key.close()  # Close the client socket.
        self.run_event.set()  # Signal the server to stop running.
        self.handle_event.set()  # Signal to stop handling clients.
        self.server_socket.close()  # Close the server socket.

    def get_clients_number(self):
        """
        Return the number of connected clients.
        """
        return len(self.clients)

    def handle_client(self, client_socket):
        """
        Handle communication with a connected client.
        Receives messages and broadcasts them to other clients.
        """
        while not self.handle_event.is_set():
            message = ""
            try:
                message = client_socket.recv(4096).decode()  # Receive message from client.
            except:
                # In case of any exception (e.g., client disconnect), broadcast exit and close client.
                if client_socket in self.clients:
                    self.broadcast(client_socket, 'exit')
                    self.close_client(client_socket)

            self.broadcast(client_socket, message)  # Broadcast the received message.

            if 'exit' == message:
                break  # Exit the loop if client wants to disconnect.

        self.close_client(client_socket)  # Ensure the client is removed from the list.

    def run(self):
        """
        Start the TCP server and listen for incoming client connections.
        Handles KeyboardInterrupt for graceful shutdown.
        """
        print("Server is running...\nPress CTRL+C to shut down the server.")
        try:
            while not self.run_event.is_set():
                if self.accept_client():
                    # Start a new thread to handle the connected client.
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(list(self.clients.keys())[-1],)
                    )
                    thread.start()
        except KeyboardInterrupt:
            pass  # Handle CTRL+C gracefully.
        self.shutdown()  # Ensure server is shutdown.


# -------------------- TCP Client Implementation -------------------- #
class ClientTCP:
    def __init__(self, client_name, server_port):
        """
        Initialize the TCP client with a name and server port.
        Sets up the client socket and threading events.
        """
        self.server_addr = 'localhost'
        self.client_socket = socket(AF_INET, SOCK_STREAM)  # Create a TCP socket.
        self.server_port = server_port
        self.client_name = client_name
        self.exit_run = threading.Event()  # Event to control client run state.
        self.exit_receive = threading.Event()  # Event to control receiving messages.

    def connect_server(self):
        """
        Connect to the TCP server and send the client's name.
        Receives a welcome message if the name is accepted.
        """
        self.client_socket.connect((self.server_addr, self.server_port))  # Connect to server.
        self.client_socket.send(self.client_name.encode())  # Send client name.
        response = self.client_socket.recv(4096).decode()  # Receive server response.

        if 'Welcome' in response:
            return True  # Successfully connected.
        return False  # Name was taken or connection failed.

    def send(self, text):
        """
        Send a message to the server.
        """
        if text:
            self.client_socket.send(text.encode())

    def receive(self):
        """
        Continuously receive messages from the server.
        Prints messages and handles server shutdown or disconnection.
        """
        try:
            while not self.exit_run.is_set():
                message = self.client_socket.recv(4096).decode()  # Receive message from server.

                if not message:
                    print("Disconnected from server.")
                    self.exit_run.set()
                    break

                if message.lower() == "server-shutdown":
                    print("Server is shutting down.")
                    self.exit_run.set()
                    break

                print(message)  # Display the received message.

        except Exception as e:
            if not self.exit_run.is_set():
                print(f"Error receiving message: {e}")
                self.exit_run.set()

    def run(self):
        """
        Run the TCP client.
        Connects to the server, starts the receive thread, and handles user input.
        """
        if self.connect_server():
            print("Joined Server\nType 'exit' to leave.")
            # Start a thread to receive messages from the server.
            receive_thread = threading.Thread(target=self.receive)
            receive_thread.daemon = True  # Ensures thread exits when main program does.
            receive_thread.start()
        else:
            print("Name already taken. Please choose a different name.")
            self.client_socket.close()
            return

        try:
            while not self.exit_run.is_set():
                message = input()  # Get user input.
                self.send(message)  # Send the message to the server.

                if message.lower() == 'exit':
                    self.exit_run.set()
                    break

        except KeyboardInterrupt:
            self.send('exit')  # Send exit message on CTRL+C.
            self.exit_run.set()

        finally:
            self.exit_receive.set()
            self.client_socket.close()  # Close the socket.
            print("Client has exited.")


# -------------------- UDP Server Implementation -------------------- #
class ServerUDP:
    def __init__(self, server_port):
        """
        Initialize the UDP server with the specified port.
        Sets up the server socket and initializes necessary variables.
        """
        self.server_port = server_port
        self.server_socket = socket(AF_INET, SOCK_DGRAM)  # Create a UDP socket.
        self.server_socket.bind(('localhost', self.server_port))  # Bind the socket to localhost and the specified port.
        self.clients = {}  # Dictionary to store client addresses and their corresponding names.
        self.messages = []  # List to store messages for broadcasting.
        self.running = True  # Flag to control the main loop.

    def accept_client(self, client_addr, message):
        """
        Accept a new UDP client.
        Checks for unique client name and sends welcome or rejection message.
        """
        if message in self.clients.values():
            self.server_socket.sendto("Name already taken".encode(), client_addr)  # Inform the client that the name is taken.
            return False  # Indicate that the client was not accepted.

        self.server_socket.sendto(f"Welcome {message}".encode(), client_addr)  # Send a welcome message to the client.
        print(f"Welcome {message}")
        self.clients[client_addr] = message  # Add the client to the clients dictionary.
        self.messages.append((client_addr, f"User {message} has joined"))  # Add a join message to the messages list.
        self.broadcast()  # Broadcast the join message to other clients.
        return True  # Indicate that the client was successfully accepted.

    def close_client(self, client_addr):
        """
        Remove a client from the clients dictionary.
        Broadcasts a departure message to other clients.
        """
        if client_addr in self.clients:
            client_name = self.clients.pop(client_addr)  # Remove the client from the dictionary.
            departure_message = f"User {client_name} has left"  # Create a departure message.
            self.messages.append((client_addr, departure_message))  # Add the departure message to the messages list.
            self.broadcast()  # Broadcast the departure message to other clients.
            print(f"Client '{client_name}' disconnected.")
            return True  # Indicate that the client was successfully removed.
        return False  # Indicate that the client was not found.

    def get_clients_number(self):
        """
        Return the number of connected UDP clients.
        """
        return len(self.clients)

    def broadcast(self):
        """
        Broadcast messages to all connected clients except the sender.
        """
        if not self.messages:
            return  # No messages to broadcast.

        sender_addr, message_str = self.messages[-1]  # Get the latest message.

        if message_str.startswith("User ") and (message_str.endswith("has joined") or message_str.endswith("has left")):
            formatted_message = message_str  # Join or leave message.
        else:
            sender_name = self.clients.get(sender_addr)
            formatted_message = f"{sender_name}: {message_str}"  # Regular message.

        for client_addr in self.clients:
            if client_addr != sender_addr:  # Don't send the message back to the sender.
                try:
                    self.server_socket.sendto(formatted_message.encode(), client_addr)  # Send the message.
                except Exception as e:
                    print(f"Error broadcasting message to {self.clients[client_addr]}: {e}")

    def shutdown(self):
        """
        Shutdown the UDP server gracefully.
        Sends a shutdown message to all clients and closes the server socket.
        """
        print("\nShutting down server...")
        for client_addr in list(self.clients.keys()):
            try:
                self.server_socket.sendto("server-shutdown".encode(), client_addr)  # Notify the client about shutdown.
                print(f"Sent shutdown message to {self.clients[client_addr]}")
                self.close_client(client_addr)  # Remove the client.
            except Exception as e:
                print(f"Error sending shutdown to {self.clients[client_addr]}: {e}")

        self.server_socket.close()  # Close the server socket.
        self.running = False  # Stop the main loop.
        print("Server shutdown complete.")

    def run(self):
        """
        Start the UDP server and listen for incoming messages.
        Handles client join, exit, and regular messages.
        """
        print("Server is running...\nPress CTRL+C to shut down the server.")

        while self.running:
            try:
                # Use select to wait for incoming data with a timeout of 1 second.
                readable, _, _ = select.select([self.server_socket], [], [], 1)

                if readable:
                    # There is data to read on the server socket.
                    message, client_addr = self.server_socket.recvfrom(4096)  # Receive message.
                    message = message.decode().strip()  # Decode and strip whitespace.

                    if ':' in message:
                        # Message format: "name:message".
                        client_name, msg = message.split(':', 1)

                        if msg.lower() == 'join':
                            self.accept_client(client_addr, client_name)
                        elif msg.lower() == 'exit':
                            self.close_client(client_addr)
                        else:
                            if client_addr in self.clients:
                                self.messages.append((client_addr, msg))  # Add regular message.
                                self.broadcast()
                    else:
                        # Message without colon.
                        if message.lower() == 'join':
                            self.accept_client(client_addr, message)
                        elif message.lower() == 'exit':
                            self.close_client(client_addr)
                        elif client_addr in self.clients:
                            self.messages.append((client_addr, message))  # Add regular message.
                            self.broadcast()
                else:
                    pass  # No data received within the timeout period.

            except KeyboardInterrupt:
                self.shutdown()  # Shutdown server on CTRL+C.
            except Exception as e:
                print(f"An error occurred: {e}")
                self.shutdown()  # Shutdown server on any other exception.


# -------------------- UDP Client Implementation -------------------- #
class ClientUDP:
    def __init__(self, client_name, server_port):
        """
        Initialize the UDP client with a name and server port.
        Sets up the client socket and threading events.
        """
        self.server_addr = 'localhost'
        self.client_socket = socket(AF_INET, SOCK_DGRAM)  # Create a UDP socket.
        self.server_port = server_port
        self.client_name = client_name
        self.exit_run = threading.Event()  # Event to control client run state.
        self.exit_receive = threading.Event()  # Event to control receiving messages.

    def connect_server(self):
        """
        Connect to the UDP server by sending a join message.
        Receives a welcome message if the name is accepted.
        """
        self.send('join')  # Send join request.
        message, server_addr = self.client_socket.recvfrom(4096)  # Receive response.
        message = message.decode()

        if 'Welcome' in message:
            return True  # Successfully connected.
        return False  # Name was taken or connection failed.

    def send(self, text):
        """
        Send a message to the UDP server with the client's name prefixed.
        """
        self.client_socket.sendto(
            f"{self.client_name}:{text}".encode(),
            (self.server_addr, self.server_port)
        )

    def receive(self):
        """
        Continuously receive messages from the server.
        Prints messages and handles server shutdown.
        """
        while not self.exit_run.is_set():
            message, server_addr = self.client_socket.recvfrom(4096)  # Receive message.
            message = message.decode()
            print(message)  # Display the received message.

            if message == "server-shutdown":
                self.exit_run.set()  # Signal to stop running.
                self.exit_receive.set()  # Signal to stop receiving.

    def run(self):
        """
        Run the UDP client.
        Connects to the server, starts the receive thread, and handles user input.
        """
        if self.connect_server():
            print("Joined Server\nType 'exit' to leave.")
            # Start a thread to receive messages from the server.
            receive_thread = threading.Thread(target=self.receive)
            receive_thread.daemon = True  # Ensures thread exits when main program does.
            receive_thread.start()
        else:
            print("Name already taken. Please choose a different name.")
            self.client_socket.close()
            return

        try:
            while not self.exit_run.is_set():
                message = input()  # Get user input.
                self.send(message)  # Send the message to the server.

                if message.lower() == 'exit':
                    self.exit_run.set()  # Signal to stop running.
                    self.exit_receive.set()  # Signal to stop receiving.
                    break

        except KeyboardInterrupt:
            # Handle CTRL+C by sending exit message.
            self.client_socket.sendto('exit'.encode(), (self.server_addr, self.server_port))
            self.exit_run.set()
            self.client_socket.close()

