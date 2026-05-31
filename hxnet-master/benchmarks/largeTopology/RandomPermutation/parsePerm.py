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
    if ("jellyfish" in names and "hx2" in names):
        return "Hx2Mesh\nJellyfish"
    elif ("jellyfish" in names and "hx4" in names):
        return "Hx4Mesh\nJellyfish"
    elif (names == "hx2"):
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
    detected_num_nodes = set()
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

                        match_nodes = re.search(r"EMBER: numNodes=(\d+)", line)
                        if match_nodes:
                            detected_num_nodes.add(int(match_nodes.group(1)))

                        match = re.search(r"STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            tmp_size = ((int(match.group(6))))
                            tmp_time = ((int(match.group(5))))
                            if tmp_time > 0:
                                min_bw = tmp_size / tmp_time
                                bw_map[subdirectory].append(min_bw * 8)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots()
    fig = plt.gcf()
    fig.set_size_inches( 12.0, 5)
    pa = sns.color_palette("tab20")

    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    plot_names = []
    y_data = []
    for key in sortednames:
        if (len(bw_map[key]) > 0):
            y_data.append(bw_map[key])
            plot_names.append(key)
            print("-- {} --".format(key))
            avg = str(statistics.mean(bw_map[key]))
            median =  str(statistics.median(bw_map[key]))
            high_99 = str(np.percentile(bw_map[key], 99))
            low_1 = str(np.percentile(bw_map[key], 1))
            print("Avg {} - Median {} - High 99% {} - Low 1% {}\n".format(avg, median, high_99, low_1))

    # Build color list matching topology order
    color_map = {
        "hx2": pa.as_hex()[0],
        "hx4": pa.as_hex()[1],
        "torus": pa.as_hex()[2],
        "dragonfly": pa.as_hex()[3],
        "fattree": pa.as_hex()[4],
        "fattree50": pa.as_hex()[5],
        "fattree75": pa.as_hex()[6],
        "fattree80": pa.as_hex()[6],
        "hyperx": "#8c8c8c",
    }
    list_colors = []
    for key in plot_names:
        if "jellyfish" in key and "hx2" in key:
            list_colors.append(pa.as_hex()[8])
        elif "jellyfish" in key and "hx4" in key:
            list_colors.append(pa.as_hex()[9])
        elif key in color_map:
            list_colors.append(color_map[key])
        else:
            list_colors.append(pa.as_hex()[len(list_colors) % len(pa.as_hex())])

    display_names = [adapt_names(ele) for ele in plot_names]
    data_plot = pd.DataFrame({"X": display_names, "Y": y_data})

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
    if len(detected_num_nodes) == 1:
        title_nodes = "%d nodes" % next(iter(detected_num_nodes))
    elif detected_num_nodes:
        title_nodes = "%s nodes" % "/".join(str(n) for n in sorted(detected_num_nodes))
    else:
        title_nodes = "unknown nodes"
    plt.title("Random Permutation (1x64 MiB) - %s" % title_nodes, fontsize=23)
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
