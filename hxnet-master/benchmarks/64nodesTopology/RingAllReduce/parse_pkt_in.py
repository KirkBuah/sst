# %%
from cmath import sqrt
from csv import list_dialects
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
    elif (names == "fattree80"):
        return "FatTree 80% Block."
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
            #time[subdirectory] = list()

            if (subdirectory != "hx2"):
                continue

            for file in filelist:
                #print("Dir {} + File {}".format(subdirectory, file))
                #x_sizes[subdirectory].append(int(file))
                if (file != "1048576"):
                    continue
                min_bw = 100000000000

                list_src = []
                for i in range(64):
                    list_src.append([])

                with open(os.path.join(root, subdirectory, file)) as fp:
                    Lines = fp.readlines()
                    count = 0
                    for line in Lines:

                        match = re.search("PKTOUT (\d+) RTR.(\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            time = int(match.group(1))
                            rtr = int(match.group(2))
                            src = int(match.group(3))
                            dest = int(match.group(4))
                            size = int(match.group(5))
                            list_src[src].append(time)

                        match = re.search("STATS (\d+) (\d+) EMBER (\d+) (\d+) (\d+) (\d+)", line)
                        if match:
                            #tmp_bytes = ((int(match.group(6))))
                            tmp_bytes = count
                            tmp_time = ((int(match.group(5))))
                            #print("{} {}".format(tmp_bytes, tmp_time))
                            print(os.path.join(root, subdirectory, file))
                            if (tmp_bytes / tmp_time < min_bw):
                                min_bw = tmp_bytes / tmp_time



    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots()
    sortednames=sorted(bw_map.keys(), key=lambda x:x.lower())
    most_x = []
    '''
    for key in sortednames:
        x_data = x_sizes[key]
        y_data = bw_map[key]
        y_data_new = []
        x_data_new = []
        time_bw = time[key]
        if (len(x_data) > len(most_x)):
            most_x = x_data
        #print("topo {} {}".format(key,x_data))
        if (key == "fattree" or key == "fattree50" or key == "fattree80" or key == "dragonfly" and adapt_plane):
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
        '''
    print(list_src)
    for i in range(64):
        y_data = i
        x_data = list_src[i]
        print("len is {}".format(len(list_src[i])))
        x_data = x_data[:len(x_data)-1400]
        data_plot = pd.DataFrame({"X":x_data, "Y":y_data})
        
        sns.lineplot(x = "X", y = "Y", data=data_plot, marker='d', ax=ax)

    #ax.set_ylim([-100, 1650])
    plt.show()

    plt.xlabel("Time")
    plt.ylabel("Src")
    plt.title("Debugging Send Machine - 64 Nodes")
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
