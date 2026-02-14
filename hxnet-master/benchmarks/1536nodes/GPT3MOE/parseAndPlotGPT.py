# %%
import os
import re
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path    
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

output_folder = 'output/'
save_folder = 'plots'
save_folder_pdf = save_folder + "/" + "pdf"
save_folder_img = save_folder + "/" + "img"
adapt_plane = True
bw_map = {}
compute_time_l = {}
bytes_sent_map = {}
time_map = {}
x_sizes = {}

def adapt_names(names):
    if (names == "hx2"):
        return "Hx2Net"
    elif (names == "hx4"):
        return "Hx4Net"
    elif (names == "torus"):
        return "2D Torus"
    elif (names == "dragonfly"):
        return "Dragonfly"
    elif (names == "fattree"):
        return "FatTree Non"
    elif (names == "fattree50"):
        return "FatTree 50%"
    elif (names == "fattree80" or names == "fattree75"):
        return "FatTree 75%"

def bytes_to_mb(list_b):
    list_mb = []
    for b in list_b:
        if (b / 1000000000000 < 1):
            value = "{}GB".format(int(b / 1000000000))
        if (b / 1000000000 < 1):
            value = "{}MB".format(int(b / 1000000))
        if (b / 1000000 < 1):
            value = "{}KB".format(int(b / 1000))

        list_mb.append(value)
    return list_mb
    

def main():
    # Iterate through results, sort them by size and parse them
    for root, subdirectories, files in os.walk(output_folder):
        for subdirectory in subdirectories:
            filelist = os.listdir(os.path.join(root, subdirectory))
            filelist = sorted(filelist,key=lambda x: int(os.path.splitext(x)[0]))

            bytes_sent_map[subdirectory] = list()
            time_map[subdirectory] = list()
            x_sizes[subdirectory] = list()
            bw_map[subdirectory] = list()
            compute_time_l[subdirectory] = list()

            for file in filelist:
                #print("Dir {} + File {}".format(subdirectory, file))
                if file != "1536":
                    continue

                x_sizes[subdirectory].append(int(file))

                min_bw = 0
                compute_time = 0

                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    for line in Lines:
                        match = re.search("STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            tmp_bytes = ((int(match.group(6))))
                            tmp_time = ((int(match.group(5))))
                            #print("{} {}".format(tmp_bytes, tmp_time))
                            if (tmp_time > min_bw):
                                min_bw = tmp_time

                        match = re.search("Rank (\d+) - Total Compute time (\d+)", line)
                        if match:
                            if ((int(match.group(2))) > compute_time):
                                compute_time = (int(match.group(2)))

                    if (min_bw == 100000000000):
                        min_bw = 0
                    bw_map[subdirectory].append(min_bw)
                    compute_time_l[subdirectory].append(compute_time)

    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots()
    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    x_values = []
    y_values = []
    for key in sortednames:
        print("--- {} ---".format(key))
        print("Runtime: {}ms - Compute Time: {}ms - Comm. OverHead: {}ms".format(bw_map[key][0]/1000000, compute_time_l[key][0]/1000000, (bw_map[key][0] - compute_time_l[key][0])//1000000))
        x_data = x_sizes[key]
        y_data = bw_map[key]
        y_data = [element * 8 for element in y_data]
        if (len(x_data) > len(most_x)):
            most_x = x_data
        y_data = [element * 1 for element in y_data]
        x_data = [element * 1 for element in x_data]
        y_values.append(y_data[0])
        x_values.append(adapt_names(key))

        
if __name__ == "__main__":
    main()


# %%
