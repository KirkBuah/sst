# %%
import os
import re
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path    
import pandas as pd
from datetime import datetime
import warnings
import numpy as np
import statistics
from matplotlib.ticker import MaxNLocator




warnings.filterwarnings("ignore")

output_folder = 'output/'
save_folder = 'plots'
save_folder_pdf = save_folder + "/" + "pdf"
save_folder_img = save_folder + "/" + "img"
adapt_plane = True
bw_map = {}
bytes_sent_map = {}
time_map = {}
x_sizes = {}

def adapt_names(names):
    if (names == "hx2"):
        return "Hx2Mesh"
    elif (names == "hx4"):
        return "Hx4Mesh"
    elif (names == "torus"):
        return "2D Torus"
    elif (names == "dragonfly"):
        return "Dragonfly"
    elif (names == "fattree"):
        return "nonblocking\nfat tree"
    elif (names == "fattree50"):
        return "fat tree\n50%\ntapered"
    elif (names == "fattree80" or names == "fattree75"):
        return "fat tree\n75%\ntapered"
    elif (names == "hyperx" or names == "fattree75"):
        return "2D HyperX\n(Hx1Mesh)"
    else:
        return names

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
    size_all_to_all = -1
    for root, subdirectories, files in os.walk(output_folder):
        for subdirectory in subdirectories:
            filelist = os.listdir(os.path.join(root, subdirectory))
            filelist = sorted(filelist,key=lambda x: int(os.path.splitext(x)[0]))

            bytes_sent_map[subdirectory] = list()
            time_map[subdirectory] = list()
            x_sizes[subdirectory] = list()
            bw_map[subdirectory] = list()

            for file in filelist:
                #print("Dir {} + File {}".format(subdirectory, file))
                x_sizes[subdirectory].append(int(file))

                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    for line in Lines:

                        match = re.search("EMBER: Motif='Alltoall bytes=(\d+)'", line)
                        if match:
                            size_all_to_all = ((int(match.group(1)))) * 1023

                        match = re.search("STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            tmp_size = ((int(match.group(6))))
                            tmp_time = ((int(match.group(5))))
                            min_bw = tmp_size / tmp_time
                            if (min_bw > 197):
                                min_bw = 197
                            bw_map[subdirectory].append(min_bw * 8)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots()
    fig = plt.gcf()
    fig.set_size_inches( 12.0, 5)
    pa = sns.color_palette()

    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    y_data = []
    for key in sortednames:
        if (len(bw_map[key]) > 0):
            y_data.append(bw_map[key])
            print("-- {} --".format(key))
            avg = str(statistics.mean(bw_map[key]))
            median =  str(statistics.median(bw_map[key]))
            high_99 = str(np.percentile(bw_map[key], 99))
            low_1 = str(np.percentile(bw_map[key], 1))
            print("Avg {} - Median {} - High 99% {} - Low 1% {}\n".format(avg, median, high_99, low_1))
    sortednames = [adapt_names(ele) for ele in sortednames]
    tmp_name = sortednames[0]
    tmp_data = y_data[0]

    sortednames = sortednames[1:4] + [tmp_name] + sortednames[4:]  
    y_data = y_data[1:4] + [tmp_data] + y_data[4:]  


    tmp_name = sortednames[6]
    tmp_data = y_data[6]
    sortednames = sortednames[0:4] + [tmp_name] + sortednames[4:6] + sortednames[7:] 
    y_data = y_data[0:4] + [tmp_data] + y_data[4:6] + y_data[7:] 


    list_colors = [pa.as_hex()[4], pa.as_hex()[5], pa.as_hex()[6], pa.as_hex()[3],  pa.as_hex()[7], pa.as_hex()[0], pa.as_hex()[1], pa.as_hex()[2]]
    list_colors = ["#7F73AF", "#8F7963", "#CF8FC0", "#C44E52", "#8C8C8C", "#4C72B0", "#DD8452", "#55A868"]
    data_plot = pd.DataFrame({"X":sortednames, "Y":y_data})
    
    print(data_plot)
    data_plot = data_plot.explode('Y')
    data_plot['Y'] = data_plot['Y'].astype('float')
    b = sns.violinplot(data=data_plot, x='X', y='Y', palette=list_colors, saturation=2)
    

    b.yaxis.set_tick_params(labelsize=17)
    ax.set_ylim(-3,1700)
    _, xlabels = plt.xticks()
    b.set_xticklabels(xlabels, size=17)

    plt.show()

    plt.xlabel("Topology", fontsize=21)
    plt.ylabel("Bandwidth (Gb/s)", fontsize=21)
    plt.title("Random Permutation (2x32 MiB) - Small Topologies (~1,000 nodes)", fontsize=23)
    #plt.legend()
    plt.show()
    b.set(ylim=(-1, 1700))
    b.yaxis.set_tick_params(labelsize=17)

    # set the x-labels with
    _, xlabels = plt.xticks()
    b.set_xticklabels(xlabels, size=16)

    ax.tick_params(tick1On=True) # "for left and bottom ticks"

    for spine in b.spines.values():
        spine.set_edgecolor('black')

    plt.tight_layout()
    Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
    Path(save_folder_img).mkdir(parents=True, exist_ok=True)
    file_name = datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
    plt.savefig(Path(save_folder_img) / (str("RandomPerm") + file_name))
    plt.savefig(Path(save_folder_pdf) / (str("RandomPerm") + file_name + ".pdf"))
        
if __name__ == "__main__":
    main()


# %%
