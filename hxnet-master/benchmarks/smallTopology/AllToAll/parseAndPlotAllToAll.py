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
bytes_sent_map = {}
time_map = {}
x_sizes = {}

def get_color(names, pa):
    if ("hx2" in names):
        return pa.as_hex()[0]
    elif ("hx4" in names):
        return pa.as_hex()[1]
    elif ("hyperx" in names):
        return pa.as_hex()[7]
    elif ("torus" in names):
        return pa.as_hex()[2]
    elif (names == "dragonfly"):
        return pa.as_hex()[3]
    elif (names == "fattree"):
        return pa.as_hex()[4]
    elif (names == "fattree50"):
        return pa.as_hex()[5]
    elif (names == "fattree80" or names == "fattree75"):
        return pa.as_hex()[6]
    else:
        return names

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
        return "FatTree Non Block."
    elif (names == "fattree50"):
        return "FatTree 50% Block."
    elif (names == "fattree80" or names == "fattree75"):
        return "FatTree 80% Block."
    else:
        return names

def bytes_to_mb(list_b):
    list_mb = []
    for b in list_b:
        if (b / 1000000000000 < 1):
            value = "{}GB".format(int(b / (1024*1024*1024)))
        if (b / 1000000000 < 1):
            value = "{}MB".format(int(b / (1024*1024)))
        if (b / 1000000 < 1):
            value = "{}KB".format(int(b / 1024))
        if (b / 1000 < 1):
            value = "{}B".format(int(b / 1))

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

                min_bw = 100000000000

                num_nodes = 1024  # default for original ~1000-node runs
                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    for line in Lines:

                        match_nodes = re.search(r"EMBER: numNodes=(\d+)", line)
                        if match_nodes:
                            num_nodes = int(match_nodes.group(1))

                        match = re.search("EMBER: Motif='AllPingPong messageSize=(\d+)'", line)
                        if match:
                            size_all_to_all = ((int(match.group(1)))) * (num_nodes - 1)

                        match = re.search("STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            tmp_time = ((int(match.group(5))))
                            #print("{} {}".format(tmp_bytes, tmp_time))
                            #print(os.path.join(root, subdirectory, file))
                            if (size_all_to_all / tmp_time < min_bw):
                                min_bw = size_all_to_all / tmp_time

                    if (min_bw == 100000000000):
                        min_bw = 0
                    bw_map[subdirectory].append(min_bw)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots()
    fig = plt.gcf()
    fig.set_size_inches( 9, 4.8)
    pa = sns.color_palette()
    
    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    for key in sortednames:
        x_data = x_sizes[key]
        y_data = bw_map[key]
        y_data = [element * 8 for element in y_data]
        if (len(x_data) > len(most_x)):
            most_x = x_data
        #print("topo {} {}".format(key,x_data))
        if (key == "fattree" or key == "fattree50" or key == "fattree80" or key == "dragonfly" and adapt_plane):
            y_data = [element * 1 for element in y_data]
            x_data = [element * 1 for element in x_data]
        data_plot = pd.DataFrame({"X":x_data, "Y":y_data})
        print(key)
        print(data_plot)
        my_color = get_color(key, pa)
        key = adapt_names(key)
        a =sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
        #'''
    
    '''
    points_hyperx_x = [16, 64, 256, 1024, 4096, 65536, 1048576]
    points_hyperx_y = [22, 39, 211, 576, 861, 999, 1280]    
    data_plot = pd.DataFrame({"X":points_hyperx_x, "Y":points_hyperx_y})
    my_color = "#ADD8E6"
    a =sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', ax=ax, linewidth=3.2, color=my_color)
    '''

    ax.set_xscale('log', base=2)
    locs, labels = plt.xticks()
    #print(locs)
    ax.set_xticklabels(bytes_to_mb(locs))
    a.yaxis.set_tick_params(labelsize=17)
    ax.set_ylim(-1,1620)
    # set the x-labels with
    _, xlabels = plt.xticks()
    #print(a.get_yticks())
    a.set_xticklabels(xlabels, size=17)

    ax.tick_params(tick1On=True) # "for left and bottom ticks"

    for spine in a.spines.values():
        spine.set_edgecolor('black')

    '''every_nth = 100
    for n, label in enumerate(ax.xaxis.get_ticklabels()):
        if n % every_nth == 0:
            label.set_visible(False)'''

    plt.show()

    #ax.set_ylim([0, 150])

    plt.xlabel("Message Size", fontsize=21)
    plt.ylabel("Throughput (Gb/s)", fontsize=21)
    plt.title("AllToAll - Small Topologies (~1,000 nodes)", fontsize=23)
    #plt.legend()
    plt.legend([],[], frameon=False)
    plt.show()

    plt.tight_layout()
    Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
    Path(save_folder_img).mkdir(parents=True, exist_ok=True)
    file_name = datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
    plt.savefig(Path(save_folder_img) / (str("AllToAll") + file_name))
    plt.savefig(Path(save_folder_pdf) / (str("AllToAll") + file_name + ".pdf"))

        
if __name__ == "__main__":
    main()


# %%
