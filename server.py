import time
import subprocess
import os
import sys
import socket

# Function to read parameters from config file
def read_config(config_file="config.txt"):
    config = {}
    with open(config_file, "r") as file:
        for line in file:
            if "=" in line:
                key, value = line.strip().split("=")
                config[key.strip()] = value.strip()
    return config

# Function to execute a shell command
def execute_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{command}' failed with error: {e}")

# Function to restore the container from the checkpoint
def restore_container_from_checkpoint(checkpoint_filename, container_name, checkpoint_counter):
    restore_name = f"{container_name}_restore_{checkpoint_counter}"
    print(f"Restoring container {container_name} from checkpoint {checkpoint_filename}...")
    execute_command(f"sudo podman container restore --import={checkpoint_filename} --name {restore_name}")
    print(f"Container {container_name} restored successfully as {restore_name}.")
    # Optionally, resume the restored container
    execute_command(f"sudo podman container start {restore_name}")
    print(f"Container {restore_name} resumed.")

def process_checkpoint_file(checkpoint_filename, container_name, checkpoint_counter):
    """Process the checkpoint file after receiving it."""
    print(f"Processing checkpoint: {checkpoint_filename}")
    restore_container_from_checkpoint(checkpoint_filename, container_name, checkpoint_counter)

# Read parameters from config file
config = read_config("config.txt")

checkpoint_directory = config["checkpoint_directory"]
protocol = config.get("protocol", "TCP").upper()  # Read the protocol from config file
port = int(config.get("port", 22))  # Read the port from config file

# Check if the checkpoint directory exists
if not os.path.exists(checkpoint_directory):
    print(f"Checkpoint directory does not exist: {checkpoint_directory}")
    sys.exit(1)

print(f"Server is listening for checkpoint files...")

# To keep track of checkpoint file versions
checkpoint_counter = 0

"""
def handle_udp_connection():
    #Handle incoming UDP connections
    global checkpoint_counter
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('', port)  # Use the port from config file
    sock.bind(server_address)
    print(f"Listening for UDP connections on port {port}...")

    # Fetch container name from config
    container_name = config["container_name"]  # Assuming this is defined in your config.txt

    # Create a dictionary to track chunked files for each checkpoint
    checkpoint_chunks = {}

    while True:
        # Receive the data in chunks
        data, address = sock.recvfrom(4096)  # Buffer size 4096
        if data:
            # We expect the client to send chunked files with the same filename
            checkpoint_filename = f"{container_name}_received_{checkpoint_counter}.tar"

            # Check if this is the first chunk for the checkpoint or a new one
            if checkpoint_filename not in checkpoint_chunks:
                checkpoint_chunks[checkpoint_filename] = []

            # Append the received chunk to the corresponding checkpoint file
            checkpoint_chunks[checkpoint_filename].append(data)
            print(f"Received chunk from {address}, storing part of {checkpoint_filename}")

            # Check if all 10 chunks for this checkpoint have been received
            # Assuming the client divides each checkpoint into 10 chunks
            if len(checkpoint_chunks[checkpoint_filename]) == 10:
                # Write the complete checkpoint file
                with open(os.path.join(checkpoint_directory, checkpoint_filename), 'wb') as f:
                    for chunk in checkpoint_chunks[checkpoint_filename]:
                        f.write(chunk)
                print(f"Received full checkpoint: {checkpoint_filename}")
                
                # Process the checkpoint after receiving all parts
                process_checkpoint_file(os.path.join(checkpoint_directory, checkpoint_filename), container_name, checkpoint_counter)

                # Reset checkpoint chunks for the next one
                checkpoint_chunks = {}
                checkpoint_counter += 1  # Increment the checkpoint counter for the next checkpoint

"""

def process_tcp_checkpoint():
    """Process incoming TCP checkpoint (via rsync)."""
    global checkpoint_counter
    while True:
        try:
            checkpoint_files = os.listdir(checkpoint_directory)
            if checkpoint_files:
                for checkpoint_file in checkpoint_files:
                    if checkpoint_file.endswith(".tar"):
                        checkpoint_path = os.path.join(checkpoint_directory, checkpoint_file)
                        checkpoint_counter = int(checkpoint_file.split('_')[-1].split('.')[0])
                        container_name = checkpoint_file.split('_')[0]
                        process_checkpoint_file(checkpoint_path, container_name, checkpoint_counter)
                        os.remove(checkpoint_path)
                        print(f"Checkpoint file {checkpoint_file} processed and removed.")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopping server...")
            break

def process_files():
    """Process checkpoint files in the directory."""
    global checkpoint_counter
    try:
        checkpoint_files = os.listdir(checkpoint_directory)
        if checkpoint_files:
            for checkpoint_file in checkpoint_files:
                if checkpoint_file.endswith(".tar"):
                    checkpoint_path = os.path.join(checkpoint_directory, checkpoint_file)
                    checkpoint_counter = int(checkpoint_file.split('_')[-1].split('.')[0])
                    container_name = checkpoint_file.split('_')[0]
                    process_checkpoint_file(checkpoint_path, container_name, checkpoint_counter)
                    os.remove(checkpoint_path)
                    print(f"Checkpoint file {checkpoint_file} processed and removed.")
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping server...")

# Main server loop
#if protocol == "UDP":
    # Start handling UDP transfer
    #handle_udp_connection()
if protocol == "TCP":
    # Start handling TCP transfer (via rsync)
    process_tcp_checkpoint()
else:
    print(f"Unknown protocol {protocol}. Exiting.")
    sys.exit(1)
