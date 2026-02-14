import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path    
from datetime import datetime
import matplotlib.patches as mpatches


output_folder = 'output/'
save_folder = 'plots'
save_folder_pdf = save_folder + "/" + "pdf"
save_folder_img = save_folder + "/" + "img"

hx2 = [3.72, 2.6, 1.96, 4.22, 2.10, 0.49,
                                 1.41, 1.52, 1.41, 2.473, 1.84, 1.87,  
                                 0.85, 0.532, 0.43, 0.553, 0.96, 0.497,
                                 2.464, 1.71, 1.292, 3.362, 1.73, 1.01,
                                 4.0, 3.26, 3.14, 5.15, 1.15, 1.431]
hx4 = [7.76, 5.4, 4.06, 8.81, 4.37, 1.01,
                                 1.53, 1.64, 1.53, 2.693, 2.0, 2.03298,  
                                 2.73, 1.729, 1.41, 1.7151, 3.12, 1.61,
                                 2.971, 2.06, 1.54, 4.04, 2.07, 1.2,
                                 5.6, 4.56, 4.4, 7.26, 1.6, 2.074]



#create DataFrame Hx2
df = pd.DataFrame({'AB': ['1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6'],
                   'Relative Cost Saving': hx2,
                   'DNN Load': ['ResNet', 'ResNet', 'ResNet', 'ResNet',  'ResNet', 'ResNet',
                            'GPT-3', 'GPT-3', 'GPT-3', 'GPT-3',  'GPT-3', 'GPT-3',
                            'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE',
                            'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow',
                            'DLRM', 'DLRM', 'DLRM', 'DLRM', 'DLRM', 'DLRM']})

df1 = pd.DataFrame({'AB': ['1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6',
                           '1', '2', '3', '4', '5', '6'],
                   'Relative Cost Saving': hx4,
                   'DNN Load': ['ResNet', 'ResNet', 'ResNet', 'ResNet',  'ResNet', 'ResNet',
                            'GPT-3', 'GPT-3', 'GPT-3', 'GPT-3',  'GPT-3', 'GPT-3',
                            'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE', 'GPT-3\nMOE',
                            'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow',
                            'DLRM', 'DLRM', 'DLRM', 'DLRM', 'DLRM', 'DLRM']})

#set seaborn plotting aesthetics
sns.set(style='whitegrid')
fig = plt.gcf()
fig, (ax1, ax2) = plt.subplots(ncols=2, sharey=True)
fig.set_size_inches( 12.0, 4.4)

# Create colors
colors = []
for i in hx2:
    if i < 1:
        colors.append("#C44E52")
    else:
        colors.append("#55A868")

# Create colors
colors4 = []
for i in hx4:
    if i < 0.99:
        colors4.append("#C44E52")
        print("CCA")
    else:
        colors4.append("#55A868")
#colors = colors[:-12]
print(colors4)
#create grouped bar chart
colors = ["#7F73AF", "#8F7963", "#CF8FC0", "#C44E52", "#8C8C8C", "#55A868"]
colors4 = ["#7F73AF", "#8F7963", "#CF8FC0", "#C44E52", "#8C8C8C", "#55A868"]
ax11 = sns.barplot(x='DNN Load', y='Relative Cost Saving', hue='AB', data=df, palette=colors, ax = ax1, saturation=1)
ax22 = sns.barplot(x='DNN Load', y='Relative Cost Saving', hue='AB', data=df1, palette=colors4, ax = ax2, saturation=1) 
ax11.set_ylim(0,9.9)
ax11.set_xlabel("DNN Workload",fontsize=17.5)
ax11.set_ylabel("Relative Cost Saving",fontsize=17.5)
ax22.set_xlabel("DNN Workload",fontsize=17.5)
ax22.set_ylabel("Relative Cost Saving",fontsize=17.5)


for container in ax11.containers:
    ax11.bar_label(container, fmt='%.1f', fontsize=10.2, rotation=90, padding=1.8)

for container in ax22.containers:
    ax22.bar_label(container, fmt='%.1f', fontsize=10.2, rotation=90, padding=1.8)

ax11.axhline(y=0.95, ls='--', c='black', alpha=0.36)
ax22.axhline(y=0.95, ls='--', c='black', alpha=0.36)

ax1.set_title("Hx2Mesh", fontsize=19)
ax2.set_title("Hx4Mesh", fontsize=19)
ax11.patch.set_linewidth('1') 
ax11.patch.set_edgecolor('black') 
ax22.patch.set_linewidth('1') 
ax22.patch.set_edgecolor('black') 

# Set the borders to a given color...
for ax in (ax11,ax22):
    for spine in ax.spines.values():
        spine.set_edgecolor('black')

#sns.despine(bottom = True, left = True)
fig.suptitle('Relative Cost Savings (Communication Overhead of DNN Workloads)', fontsize=20, y=0.942)

ax11.yaxis.set_tick_params(labelsize=16)
# set the x-labels with
_, xlabels = plt.xticks()
print(ax11.get_yticks())
ax11.set_xticklabels(xlabels, size=16)
ax22.yaxis.set_tick_params(labelsize=16)
# set the x-labels with
_, xlabels = plt.xticks()
print(ax22.get_yticks())
ax22.set_xticklabels(xlabels, size=16)

ax11.tick_params(tick1On=True) # "for left and bottom ticks"
ax11.tick_params(axis="x", bottom=False)


plt.legend([],[], frameon=False)
ax11.legend_.remove()
ax22.legend_.remove()
circ1 = mpatches.Patch( facecolor=colors[0],alpha=1,label='nonblocking fat tree')
circ2 = mpatches.Patch( facecolor=colors[1],alpha=1,label='fat tree 50% tapered')
circ3 = mpatches.Patch( facecolor=colors[2],alpha=1,label='fat tree 75% tapered')
circ4 = mpatches.Patch(facecolor=colors[3],alpha=1,label='Dragonfly')
circ5 = mpatches.Patch(facecolor=colors[4],alpha=1,label='2D HyperX')
circ6 = mpatches.Patch(facecolor=colors[5],alpha=1,label='2D Torus')
ax11.legend(handles = [circ1,circ2,circ3,circ4,circ5,circ6],ncol=2,)
plt.setp(ax11.get_legend().get_texts(), fontsize='15.0') # for legend text

plt.tight_layout(rect=[0.01, -0.03, 1, 0.999])
Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
Path(save_folder_img).mkdir(parents=True, exist_ok=True)
file_name = datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
plt.savefig(Path(save_folder_img) / (str("RingAllReduce") + file_name))
plt.savefig(Path(save_folder_pdf) / (str("RingAllReduce") + file_name + ".pdf"))