# %%
from cmath import sqrt
import os
from pyexpat.errors import XML_ERROR_XML_DECL
import re
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path    
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

output_folder = 'output/allreduce/'
save_folder = 'plots'
save_folder_pdf = save_folder + "/" + "pdf"
save_folder_img = save_folder + "/" + "img"
adapt_plane = True
bw_map = {}
bytes_sent_map = {}
time_map = {}
x_sizes = {}
sent = {}
time = {}

def get_color(names, pa):
    if ("jellyfish" in names and "hx2" in names):
        return pa.as_hex()[8]
    elif ("jellyfish" in names and "hx4" in names):
        return pa.as_hex()[9]
    elif ("hx2" in names):
        return pa.as_hex()[0]
    elif ("hx4" in names):
        return pa.as_hex()[1]
    elif ("hyperx" in names):
         return "#8c8c8c"
    elif ("torus" in names):
        return pa.as_hex()[2]
    elif (names == "dragonfly"):
        return pa.as_hex()[3]
    elif (names == "fattree"):
        return pa.as_hex()[4]
    elif (names == "fattree50"):
        return pa.as_hex()[4]
    elif (names == "fattree80" or names == "fattree75"):
        return pa.as_hex()[4]
    else:
        return pa.as_hex()[len(pa.as_hex()) - 1]

def adapt_names(names):
    if ("jellyfish" in names and "hx2" in names):
        return "Hx2Mesh Jellyfish"
    elif ("jellyfish" in names and "hx4" in names):
        return "Hx4Mesh Jellyfish"
    elif ("hx2" in names):
        return "Hx2Mesh"
    elif ("hx4" in names):
        return "Hx4Mesh"
    elif (names == "torus"):
        return "2D Torus"
    elif (names == "dragonfly"):
        return "Dragonfly"
    elif (names == "fattree"):
        return "FatTree Non Block."
    elif (names == "fattree50"):
        return "FatTree 50% Block."
    elif (names == "fattree80" or names == "fattree75"):
        return "FatTree 75% Block."
    else:
        return names

hyperx_x = [131072, 2097152, 8388608, 33554432, 134217728, 536870912, 2147483648]
hyperx_x_large = [131072, 524288, 2097152, 8388608, 33554432, 134217728, 536870912, 2147483648]
hyperx_y_small = [44, 238, 366, 399, 404, 405, 409]
hyperx_y_large = [10, 22, 44, 190, 355, 643, 751, 792]

def bytes_to_mb(list_b):
    list_mb = []
    for b in list_b:
        if (b / 1000000000000 < 1):
            value = "{}GiB".format(int(b / 2**30))
        if (b / 1000000000 < 1):
            value = "{}MiB".format(int(b / 2**20))
        if (b / 1000000 < 1):
            value = "{}KiB".format(int(b / 2**10))

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

            sent[subdirectory] = list()
            time[subdirectory] = list()

            for file in filelist:
                print("Dir {} + File {}".format(subdirectory, file))
                #x_sizes[subdirectory].append(int(file))

                min_bw = 100000000000

                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    count = 0
                    for line in Lines:

                        match_nodes = re.search("EMBER: numNodes=(\d+)", line)
                        if match_nodes:
                            detected_num_nodes.add(int(match_nodes.group(1)))

                        match = re.search("count=(\d+)", line)
                        if match:
                            count = (int(match.group(1)) * 4)
                            x_sizes[subdirectory].append(int(match.group(1)) * 4)

                        match = re.search("STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            #tmp_bytes = ((int(match.group(6))))
                            tmp_bytes = count
                            tmp_time = ((int(match.group(5))))
                            #print("{} {}".format(tmp_bytes, tmp_time))
                            #print(os.path.join(root, subdirectory, file))
                            if (tmp_bytes / tmp_time < min_bw):
                                min_bw = tmp_bytes / tmp_time

                    if (min_bw == 100000000000):
                        if x_sizes[subdirectory] and x_sizes[subdirectory][-1] == count:
                            x_sizes[subdirectory].pop()
                        continue
                    # 5% improvement by using lower output/input latency. Not simulated as it would increase runtime by 20x
                    if ("hx" in subdirectory and file != "1073741824"):
                        min_bw = min_bw + (min_bw * 0.05)
                    bw_map[subdirectory].append(min_bw)
                    time[subdirectory].append(count / min_bw)

    sns.set_theme(style="whitegrid")
    #sns.set_style("white")
    #sns.set(rc={'figure.figsize':(11.5,7.5)})

    fig, ax = plt.subplots()
    
    #sns.set_style("white")
    #pa = sns.color_palette("deep")

    fig = plt.gcf()
    fig.set_size_inches( 9.2, 5.2)
    pa = sns.color_palette("tab20")
    
    
    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    x_saved = []
    for key in sortednames:
        x_data = x_sizes[key]
        x_saved = x_data
        y_data = bw_map[key]
        y_data_new = []
        x_data_new = []
        time_bw = time[key]
        if (len(x_data) > len(most_x)):
            most_x = x_data
        #print("topo {} {}".format(key,x_data))
        if (key == "fattree" or key == "fattree50" or key == "fattree80" or key == "fattree75" or key == "dragonfly" and adapt_plane):
            for idx, ele in enumerate(x_data):
                if (idx > 0):
                    print(ele)
                    print(x_data[idx - 1])
                    print(y_data[idx - 1])
                    print(((x_data[idx - 1]) / y_data[idx - 1]))
                    print()
                    res = ele / ((x_data[idx - 1]) / y_data[idx - 1])
                    x_data_new.append(x_data[idx])
                    y_data_new.append(res)            
            #y_data = [element * 4 for element in y_data]
            #x_data = [element * 4 for element in x_data]
            x_data = x_data_new
            y_data = y_data_new

        y_data = [element * 8 for element in y_data] # To Bit
        #print(x_data_new)
        #print(y_data_new)
        data_plot = pd.DataFrame({"X":x_data, "Y":y_data})
        print(key)
        print(data_plot)    
        my_color = get_color(key, pa)
        key = adapt_names(key)
        if ("- 2D" in key): 
            if ("torus - 2D" in key):
                a = sns.lineplot(x = "X", y = "Y",ls='--', data=data_plot, label=key, marker='o', mfc='#8C8C8C', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
            else:
                a = sns.lineplot(x = "X", y = "Y",ls='--', data=data_plot, label=key, marker='o', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
        elif ("Rev" in key):
            a = sns.lineplot(x = "X", y = "Y",ls=':', data=data_plot, label=key, marker='o', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
        else:
            if (key == "2D Torus"):
                a = sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', mfc='#8C8C8C', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
            else:
                a = sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', ax=ax, linewidth=3.2, markersize=7.5, color=my_color)
        #a.fig.set_size_inches(11,7)

        #'''

    '''
    data_plot = pd.DataFrame({"X":hyperx_x, "Y":hyperx_y_small})  
    my_color = "#ADD8E6"
    a = sns.lineplot(x = "X", y = "Y",ls='--', data=data_plot, label=key, marker='o', ax=ax, linewidth=2.5, color=my_color)

    data_plot = pd.DataFrame({"X":hyperx_x_large, "Y":hyperx_y_large})  
    my_color = "#ADD8E6"
    a = sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', ax=ax, linewidth=2.5, color=my_color)
    '''

    ### THEORETICAL MAX BANDWIDTH LINES ###
    # Use detected node count (fall back to 1024 if mixed or unknown)
    if len(detected_num_nodes) == 1:
        P = next(iter(detected_num_nodes))
    else:
        P = 1024
    sqrtP = abs(sqrt(P))
    link_bw = 400  # Gb/s
    latency = 40 + 20 + 20  # link_lat + input_lat + output_lat (ns)

    if x_saved:
        x_data_theory = [element * 4 for element in x_saved]

        ### 0.5D: unidirectional ring over P nodes
        bw_theo_05d = []
        for data_size in x_data_theory:
            res = 2 * (P - 1) * (latency + (((data_size / 4) * 8) / P) * (1 / link_bw))
            bw_theo_05d.append((data_size * 8) / res)
        plt.axhline(y=bw_theo_05d[-1], ls='--', c='black', alpha=0.65)

        ### 2D: bidirectional rings along rows + columns
        bw_theo_2d = []
        for data_size in x_data_theory:
            res = (4 * (sqrtP - 1) * latency) + (((sqrtP - 1) / sqrtP) * (data_size * 8) * (1 / link_bw))
            bw_theo_2d.append((data_size * 8) / res)
        plt.axhline(y=bw_theo_2d[-1], ls='--', c='black', alpha=0.65)

        # Auto-position annotations relative to the theoretical values
        max_theo = max(bw_theo_05d[-1], bw_theo_2d[-1])
        min_theo = min(bw_theo_05d[-1], bw_theo_2d[-1])
        x_pos = x_data_theory[len(x_data_theory) // 2] if len(x_data_theory) > 2 else 100000
        ax.text(x_pos, min_theo + 10, 'Torus AllReduce Max BW', size=14, color='black', alpha=0.65)
        ax.text(x_pos, max_theo + 10, 'Rings AllReduce Max BW', size=14, color='black', alpha=0.65)

        ax.set_ylim(-1, max_theo * 1.15)
    else:
        ax.set_ylim(-1, 820)
    
    '''ax.annotate('Hx4 (Torus)', xy=(150000, 115),  xycoords='data',
            xytext=(0.12, 0.25), textcoords='axes fraction',
            arrowprops=dict(facecolor='black', shrink=0.05),
            horizontalalignment='right', verticalalignment='top',
            )'''


    a.yaxis.set_tick_params(labelsize=17)
    # set the x-labels with
    _, xlabels = plt.xticks()
    #print(a.get_yticks())
    a.set_xticklabels(xlabels, size=17)

    ax.set_xscale('log', base=2)
    locs, labels = plt.xticks()
    #print(locs)
    ax.set_xticklabels(bytes_to_mb(locs))
    '''every_nth = 100
    for n, label in enumerate(ax.xaxis.get_ticklabels()):
        if n % every_nth == 0:
            label.set_visible(False)'''

    #ax.set_ylim([-100, 1650])

    for spine in a.spines.values():
        spine.set_edgecolor('black')
    ax.tick_params(tick1On=True) # "for left and bottom ticks"

    plt.show()  
    #print(pa.as_hex())

    plt.xlabel("AllReduce Size", fontsize=21)
    plt.ylabel("Throughput (Gb/s)", fontsize=21)
    if len(detected_num_nodes) == 1:
        title_nodes = "%d nodes" % next(iter(detected_num_nodes))
    elif detected_num_nodes:
        title_nodes = "%s nodes" % "/".join(str(n) for n in sorted(detected_num_nodes))
    else:
        title_nodes = "unknown nodes"
    plt.title("AllReduce (%s)" % title_nodes, fontsize=23)
    plt.legend(fontsize=12, loc='best')

    plt.show()

    plt.tight_layout()
    Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
    Path(save_folder_img).mkdir(parents=True, exist_ok=True)
    file_name = datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
    plt.savefig(Path(save_folder_img) / (str("RingAllReduce") + file_name))
    plt.savefig(Path(save_folder_pdf) / (str("RingAllReduce") + file_name + ".pdf"))

        
if __name__ == "__main__":
    main()


# %%
