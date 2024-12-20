import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import sys
import csv
import psutil
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

# Function to calculate the total size of a directory
def get_directory_size(directory):
    total_size = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

# Function to append checkpoint data to a CSV file
def append_checkpoint_data_to_csv(filename, time_taken, cpu_usage, memory_change, total_size):
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['Time Taken (ms)', 'CPU Usage (%)', 'Dirty Memory (bytes)', 'Container Size (bytes)']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()  # Write header only once when file is created

        writer.writerow({
            'Time Taken (ms)': time_taken,
            'CPU Usage (%)': cpu_usage,
            'Dirty Memory (bytes)': memory_change,
            'Container Size (bytes)': total_size
        })

# Event handler for monitoring directory changes
class DirectoryChangeHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.first_checkpoint_done = False
        self.previous_size = get_directory_size(directory_to_monitor)
        self.container_name = config["container_name"]
        self.checkpoint_filename = None  # To store the checkpoint filename
        self.i = 0  # The counter variable starts at 0
        self.restoring = False  # Flag to prevent triggering restore again during restoration
        self.server_ip = config["server_ip"]
        self.username = config["username"]
        self.bandwidth_limit = config["bandwidth_limit"]  # Store the bandwidth limit
        self.protocol = config.get("protocol", "TCP").upper()  # Default to TCP if not specified
        self.port = config.get("port", "12345")  # Default port if not found in config

    def on_any_event(self, event):
        if event.is_directory or self.restoring:
            return  # Ignore directory events and avoid triggering during restore

        current_size = get_directory_size(directory_to_monitor)

        if current_size != self.previous_size:
            size_change = current_size - self.previous_size
            self.previous_size = current_size

            # Create the initial checkpoint
            if not self.first_checkpoint_done:
                print(f"Creating checkpoint for {self.container_name}...")
                self.checkpoint_filename = f"{config['checkpoint_path']}{self.container_name}_checkpoint_{self.i}.tar"
                execute_command(f"sudo podman container checkpoint -R -P {self.container_name} --export={self.checkpoint_filename}")
                self.first_checkpoint_done = True
                time_taken = 0  # Time taken for the initial checkpoint is set to 0
                self.i += 1
                print(f"Checkpoint created: {self.checkpoint_filename}")
            else:
                # Create subsequent checkpoints
                print(f"Creating subsequent checkpoint for {self.container_name}...")
                start_time = time.time()
                self.checkpoint_filename = f"{config['checkpoint_path']}{self.container_name}_checkpoint_{self.i}.tar"
                execute_command(f"sudo podman container checkpoint -R --with-previous {self.container_name} --export={self.checkpoint_filename}")
                end_time = time.time()
                time_taken = (end_time - start_time) * 1000  # Calculate time taken for checkpoint
                self.i += 1
                print(f"Checkpoint created: {self.checkpoint_filename}")

            # Get CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)

            # Total size of the container directory
            total_size = current_size

            # Append data to CSV
            append_checkpoint_data_to_csv('checkpoint_data.csv', time_taken, cpu_usage, abs(size_change), total_size)

            print(f"\nSending checkpoint {self.checkpoint_filename} to server...")
            self.send_checkpoint_to_server(self.checkpoint_filename)
            print(f"Checkpoint {self.checkpoint_filename} sent successfully.")

    def send_checkpoint_to_server(self, checkpoint_filename):
        if self.protocol == "TCP":
            # Use rsync to transfer the checkpoint file to the server via TCP
            rsync_command = f"sudo rsync -avz --progress"
            if self.bandwidth_limit:
                rsync_command += f" --bwlimit={self.bandwidth_limit}"

            # Adding the rest of the rsync parameters and server details
            rsync_command += f" -e 'ssh -i /home/Atesam/.ssh/id_rsa' {checkpoint_filename} {self.username}@{self.server_ip}:/home/Atesam/Documents/DS/migrated_checkpoints"

            print(f"Transferring checkpoint file {checkpoint_filename} to the server using rsync...")
            execute_command(rsync_command)
            print(f"Checkpoint file {checkpoint_filename} transferred successfully.")

        """
        elif self.protocol == "UDP":
            # Use UDP for file transfer
            print(f"Transferring checkpoint file {checkpoint_filename} to the server using UDP...")
            self.send_checkpoint_udp(checkpoint_filename)
            print(f"Checkpoint file {checkpoint_filename} transferred successfully.")

    def send_checkpoint_udp(self, checkpoint_filename):
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = (self.server_ip, int(self.port))  # Use port from config

        # Open the checkpoint file
        with open(checkpoint_filename, "rb") as f:
            # Divide the file into 10 chunks
            chunk_size = os.path.getsize(checkpoint_filename) // 10
            if os.path.getsize(checkpoint_filename) % 10 != 0:
                chunk_size += 1  # Adjust for any leftover bytes
            
            chunk_counter = 0  # Counter for chunk indexing

            # The name of the checkpoint file that will be sent to the server
            checkpoint_base_filename = os.path.basename(checkpoint_filename)
            server_filename = f"checkpoint_received_{self.i}.tar"  # Use a fixed name for reassembly

            # Send the file in chunks
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                # Send the chunk to the server
                sock.sendto(chunk, server_address)
                print(f"Sent chunk of size {len(chunk)} bytes for {server_filename} (chunk {chunk_counter})")

                chunk_counter += 1

        sock.close()
            """
# Main execution
if len(sys.argv) < 3:
    print("Usage: python3 client.py <container_name> <server_ip> [bandwidth_limit]")
    sys.exit(1)

# Read parameters from config file
config = read_config("config.txt")

directory_to_monitor = "/var/lib/containers/storage/overlay"

# Monitor directory changes for checkpointing
event_handler = DirectoryChangeHandler(config)
observer = Observer()
observer.schedule(event_handler, path=directory_to_monitor, recursive=True)

observer.start()
print(f"Migration started for container '{config['container_name']}'. Press Ctrl+C to stop.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping migration...")
finally:
    observer.stop()
    observer.join()
