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

output_folder = "output/"
save_folder = "plots"
save_folder_pdf = save_folder + "/" + "pdf"
save_folder_img = save_folder + "/" + "img"
adapt_plane = True
bw_map = {}
bytes_sent_map = {}
time_map = {}
x_sizes = {}


def adapt_names(names):
    if "jellyfish" in names and "hx2" in names:
        return "Hx2Net Jellyfish"
    elif "jellyfish" in names and "hx4" in names:
        return "Hx4Net Jellyfish"
    elif names == "hx2":
        return "Hx2Net"
    elif names == "hx4":
        return "Hx4Net"
    elif names == "torus":
        return "2D Torus"
    elif names == "dragonfly":
        return "Dragonfly"
    elif names == "fattree":
        return "FatTree Non Block."
    elif names == "fattree50":
        return "FatTree 50% Block."
    elif names == "fattree75" or names == "fattree80":
        return "FatTree 75% Block."
    else:
        return names


def bytes_to_mb(list_b):
    list_mb = []
    for b in list_b:
        if b >= 1000000000:
            value = "{}GB".format(int(b / 1000000000))
        elif b >= 1000000:
            value = "{}MB".format(int(b / 1000000))
        elif b >= 1000:
            value = "{}KB".format(int(b / 1000))
        else:
            value = "{}B".format(int(b))
        list_mb.append(value)
    return list_mb


def main():
    # Iterate through results, sort them by size and parse them
    size_all_to_all = -1
    detected_num_nodes = set()
    for root, subdirectories, files in os.walk(output_folder):
        for subdirectory in subdirectories:
            filelist = os.listdir(os.path.join(root, subdirectory))
            filelist = sorted(filelist, key=lambda x: int(os.path.splitext(x)[0]))

            bytes_sent_map[subdirectory] = list()
            time_map[subdirectory] = list()
            x_sizes[subdirectory] = list()
            bw_map[subdirectory] = list()

            for file in filelist:
                # print("Dir {} + File {}".format(subdirectory, file))

                min_bw = 100000000000

                num_nodes = 1
                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    for line in Lines:
                        match_nodes = re.search("EMBER: numNodes=(\d+)", line)
                        if match_nodes:
                            num_nodes = int(match_nodes.group(1))
                            detected_num_nodes.add(num_nodes)

                        match = re.search(
                            "EMBER: Motif='AllPingPong messageSize=(\d+)'", line
                        )
                        if match:
                            size_all_to_all = (int(match.group(1))) * (num_nodes - 1)

                        match = re.search(
                            "STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line
                        )
                        if match:
                            tmp_time = int(match.group(5))
                            # print("{} {}".format(tmp_bytes, tmp_time))
                            if size_all_to_all / tmp_time < min_bw:
                                min_bw = size_all_to_all / tmp_time

                    if min_bw == 100000000000:
                        continue
                    x_sizes[subdirectory].append(int(file))
                    bw_map[subdirectory].append(min_bw)

    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots()
    sortednames = sorted(bw_map.keys(), key=lambda x: x.lower())
    most_x = []
    for key in sortednames:
        x_data = x_sizes[key]
        y_data = bw_map[key]
        y_data = [element * 8 for element in y_data]
        if len(x_data) > len(most_x):
            most_x = x_data
        # print("topo {} {}".format(key,x_data))
        if (
            key == "fattree"
            or key == "fattree50"
            or key == "fattree80"
            or key == "fattree75"
            or key == "dragonfly"
            and adapt_plane
        ):
            y_data = [element * 1 for element in y_data]
            x_data = [element * 1 for element in x_data]
        data_plot = pd.DataFrame({"X": x_data, "Y": y_data})
        sns.lineplot(x="X", y="Y", data=data_plot, label=key, marker="o", ax=ax)
        #'''

    ### THIS ONLY FOR VALIDATION ###
    ### 1D
    for data_size in [0, 1]:
        res = 2 * (1024 - 1) * (3 * (40 + 20 + 20) + (data_size * 8 / 1024) * (1 / 400))
        bw_theo = data_size / res

    ### 2D

    ax.set_xscale("log", base=2)
    locs, labels = plt.xticks()
    ax.set_xticklabels(bytes_to_mb(locs))

    plt.show()

    # ax.set_ylim([0, 150])

    plt.xlabel("Message Size")
    plt.ylabel("Throughput (Gb/s)")
    if len(detected_num_nodes) == 1:
        title_nodes = "%d nodes" % next(iter(detected_num_nodes))
    elif detected_num_nodes:
        title_nodes = "%s nodes" % "/".join(str(n) for n in sorted(detected_num_nodes))
    else:
        title_nodes = "unknown nodes"
    plt.title("AllToAll - Large Topologies (%s)" % title_nodes)
    plt.legend()
    plt.show()

    plt.tight_layout()
    Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
    Path(save_folder_img).mkdir(parents=True, exist_ok=True)
    file_name = datetime.now().strftime("%Y-%m-%d|%H:%M:%S")
    plt.savefig(Path(save_folder_img) / (str("AllToAll") + file_name))
    plt.savefig(Path(save_folder_pdf) / (str("AllToAll") + file_name + ".pdf"))


if __name__ == "__main__":
    main()


# %%
