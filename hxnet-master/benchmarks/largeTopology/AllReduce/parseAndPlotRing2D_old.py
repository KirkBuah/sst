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

output_folder = 'output/'
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
        return "FatTree 75% Block."
    else:
        return names

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
                        min_bw = 0
                    bw_map[subdirectory].append(min_bw)
                    time[subdirectory].append(count / min_bw)

    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots()
    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    for key in sortednames:
        x_data = x_sizes[key]
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
                    res = ele / ((x_data[idx - 1]) / y_data[idx - 1])
                    x_data_new.append(x_data[idx])
                    y_data_new.append(res)            
            #y_data = [element * 4 for element in y_data]
            #x_data = [element * 4 for element in x_data]
            x_data = x_data_new
            y_data = y_data_new

        y_data = [element * 8 for element in y_data] # To Bit
        print(x_data_new)
        print(y_data_new)
        data_plot = pd.DataFrame({"X":x_data, "Y":y_data})
        print(data_plot)
        key = adapt_names(key)
        sns.lineplot(x = "X", y = "Y", data=data_plot, label=key, marker='o', ax=ax)
        #'''
    
    ### THIS ONLY FOR VALIDATION ###
    #x_data_theory = x_sizes["dragonfly"]
    x_data_theory = [512, 8192, 65536, 131072, 1048576, 2097152, 16777216, 33554432, 134217728, 2**28, 2**29]

    x_data_theory = [element * 4 for element in x_data_theory]

    ### 05D
    bw_theo = []
    last_point_1d = 0
    for data_size in x_data_theory:
        res = 2 * (16384 - 1) * (1*(40+20+20) + (((data_size / 4) * 8) / 16384) * (1 / 400))
        bw_theo.append((data_size * 8) / res)
    x_data_plot = [element * 1 for element in x_data_theory]
    #bw_theo = [element * 4 for element in bw_theo]
    data_plot = pd.DataFrame({"X":x_data_plot, "Y":bw_theo})
    sns.lineplot(x = "X", y = "Y", data=data_plot, label="0.5D Theoretical", marker='*', linestyle='--', ax=ax)
    plt.axhline(y=bw_theo[len(bw_theo) - 1], ls='--', c='#8C8C8C', alpha=0.45)

    ### 2D
    last_point_2d = 0
    x_data_theory = [512, 8192, 65536, 131072, 1048576, 2097152, 16777216, 33554432, 134217728]
    x_data_theory = [element * 4 for element in x_data_theory]
    bw_theo = []
    for data_size in x_data_theory:
        res = (4 * (abs(sqrt(16384)) - 1) * (1*(40+20+20))) + (((abs(sqrt(16384)) - 1) / (abs(sqrt(16384)))) * (data_size * 8) * (1/400))
        bw_theo.append((data_size * 8) / res)
    x_data_plot = [element * 1 for element in x_data_theory]
    #bw_theo = [float(element * 4) for element in bw_theo]
    data_plot = pd.DataFrame({"X":x_data_plot, "Y":bw_theo})
    print(bw_theo[len(bw_theo) - 1])
    plt.axhline(y=bw_theo[len(bw_theo) - 1], ls='--', c='#C9BA7E', alpha=0.45)
    sns.lineplot(x = "X", y = "Y", data=data_plot, label="2.0D Theoretical", marker='*', linestyle='--', ax=ax)

    ### 25D
    x_data_theory = [512, 8192, 65536, 131072, 1048576, 2097152, 16777216, 33554432, 134217728, 2**28, 2**29, 2**30, 2**31]
    x_data_theory = [element * 4 for element in x_data_theory]
    bw_theo = []
    last_point_25d = 0
    for data_size in x_data_theory:
        #res = (2 * (16384 - 1) * (1*(40+20+20))) + ((16384-1)/16384) * ((data_size / 2) * 8 / 16384) * (1 / 400))
        res = (2 * (16384 - 1) * (40+20+20)) + (((16384 - 1) / 16384) * ((data_size / 2 * 8) * (1 / 400)))
        
        #res = (4 * (sqrt(16384) - 1) * (4*(40+20+20))) + (((sqrt(16384) - 1) / (sqrt(16384))) * (data_size * 8) * (1/400))
        bw_theo.append((data_size * 8) / res)
        print(str(data_size / 4) + " " + str((data_size * 8) / res))
    x_data_plot = [element * 1 for element in x_data_theory]
    #bw_theo = [element * 4 for element in bw_theo]
    print((x_data_plot))
    print((bw_theo))
    data_plot = pd.DataFrame({"X":x_data_plot, "Y":bw_theo})
    sns.lineplot(x = "X", y = "Y", data=data_plot, label="2.5D Theoretical", marker='*', linestyle='--', ax=ax, alpha=0.45)
    plt.axhline(y=bw_theo[len(bw_theo) - 1], ls='--', c='#A6CADA', alpha=0.45)



    ax.set_xscale('log', base=2)
    locs, labels = plt.xticks()
    print(locs)
    ax.set_xticklabels(bytes_to_mb(locs))

    '''every_nth = 100
    for n, label in enumerate(ax.xaxis.get_ticklabels()):
        if n % every_nth == 0:
            label.set_visible(False)'''

    #ax.set_ylim([-100, 1650])
    plt.show()

    plt.xlabel("AllReduce Size")
    plt.ylabel("Throughput (Gb/s)")
    plt.title("Ring AllReduce - Large Topologies (~16k nodes)")
    plt.legend()
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
