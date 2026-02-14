from dis import dis
#from math import dist
import random
import csv
from pathlib import Path    
#import numpy

class EntryCSV:
  def __init__(self, sending_to, size,sleep):
    self.sending_to = sending_to
    self.size = size
    self.sleep = sleep

# Variables global
topo = "ddragonfly"
num_nodes = 1024
num_iterations_per_node = 1
max_node_id = num_nodes - 1
min_msg = 2**26
max_msg = 2**26
ratio_reduce_nodes = 1
distr = "random"

path = ""
if (topo == "dragonfly"):
    num_nodes = 30*32*17
    path = Path("input_dragonfly/")
else:
    num_nodes = 128*128
    path = Path("input_generic/")

path.mkdir(parents=True, exist_ok=True)

sending_to_list = [[] for i in range(num_nodes)]
receiving_from_list = [[] for i in range(num_nodes)]
nodes_list = list(range(0, num_nodes))
random.shuffle(nodes_list)

for num_rank in range(int(num_nodes/2)):
    for idx_action in range(num_iterations_per_node):
        # Get Random Size, set lower bound

        size = random.randint(min_msg,max_msg)
        sleep = random.randint(0,0)

        sending_from = nodes_list[num_rank]
        sending_to = nodes_list[num_rank + (int(num_nodes/2))]

        sending_to_list[sending_from].append(EntryCSV(sending_to, size, sleep))
        receiving_from_list[sending_to].append(EntryCSV(sending_from, size, sleep))

        sending_to_list[sending_to].append(EntryCSV(sending_from, size, sleep))
        receiving_from_list[sending_from].append(EntryCSV(sending_to, size, sleep))

for num_rank_idx in range(num_nodes):
    # Sends
    file_name = str(path) + "/send_" + str(num_rank_idx) + ".csv"
    with open(file_name, mode='w') as employee_file:
        employee_writer = csv.writer(employee_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for item in sending_to_list[num_rank_idx]:
            temp_list = []
            temp_list.append(str(item.sending_to))
            temp_list.append(str(item.size))
            temp_list.append(str(item.sleep))
            employee_writer.writerow(temp_list)

    # Reads
    file_name = str(path) + "/read_" + str(num_rank_idx) + ".csv"
    with open(file_name, mode='w') as employee_file:
        employee_writer = csv.writer(employee_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for item in receiving_from_list[num_rank_idx]:
            temp_list = []
            temp_list.append(str(item.sending_to))
            temp_list.append(str(item.size))
            temp_list.append(str(item.sleep))
            employee_writer.writerow(temp_list)
