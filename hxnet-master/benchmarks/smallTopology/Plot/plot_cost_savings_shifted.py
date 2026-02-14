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

hx2 = [3.74, 1.96, 4.12, 0.49,
                                 3.91, 2.26, 4.53, 0.798,  
                                 4.18, 2.22, 4.53, 0.597,
                                 4.64, 2.42, 5.11, 0.48]
hx4 = [7.8, 4.0, 8.6, 1.01,
                                 6.52, 3.77, 7.53, 1.3298,  
                                 7.71, 4.09, 8.51, 1.096,
                                 9.21, 4.82, 10.16, 0.951]

for idx,ele in enumerate(hx2):
    if (ele < 1):
        hx2[idx] = -(1 / ele)

for idx,ele in enumerate(hx4):
    if (ele < 1):
        hx4[idx] = -(1 / ele)
#create DataFrame Hx2
df = pd.DataFrame({'DNN Workload': ['1', '2', '3', '4',
                           '1', '2', '3', '4',
                           '1', '2', '3', '4',
                           '1', '2', '3', '4'],
                   'Relative Cost Saving': hx2,
                   'DNN Load': ['ResNet', 'ResNet', 'ResNet', 'ResNet',
                            'GPT-3', 'GPT-3', 'GPT-3', 'GPT-3',
                            'GPT-3 MOE', 'GPT-3 MOE', 'GPT-3 MOE', 'GPT-3 MOE',
                            'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow']})

df1 = pd.DataFrame({'DNN Workload': ['1', '2', '3', '4',
                           '1', '2', '3', '4',
                           '1', '2', '3', '4',
                           '1', '2', '3', '4'],
                   'Relative Cost Saving': hx4,
                   'DNN Load': ['ResNet', 'ResNet', 'ResNet', 'ResNet',
                            'GPT-3', 'GPT-3', 'GPT-3', 'GPT-3',
                            'GPT-3 MOE', 'GPT-3 MOE', 'GPT-3 MOE', 'GPT-3 MOE',
                            'CosmoFlow', 'CosmoFlow', 'CosmoFlow', 'CosmoFlow']})

#set seaborn plotting aesthetics
sns.set(style='whitegrid')
fig = plt.gcf()
fig, (ax1, ax2) = plt.subplots(ncols=2, sharey=True)
fig.set_size_inches( 12.0, 4)

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
colors = ["#7F73AF", "#CF8FC0", "#C44E52", "#55A868"]
colors4 = ["#7F73AF", "#CF8FC0", "#C44E52", "#55A868"]
ax11 = sns.barplot(x='DNN Load', y='Relative Cost Saving', hue='DNN Workload', data=df, palette=colors, ax = ax1, saturation=1)
ax22 = sns.barplot(x='DNN Load', y='Relative Cost Saving', hue='DNN Workload', data=df1, palette=colors4, ax = ax2, saturation=1) 
ax11.set_ylim(-3,11)


for container in ax11.containers:
    ax11.bar_label(container, fmt='%.1f')

for container in ax22.containers:
    ax22.bar_label(container, fmt='%.1f')

#ax11.axhline(y=1, ls='--', c='black', alpha=0.20)
#ax22.axhline(y=1, ls='--', c='black', alpha=0.20)

ax1.set_title("Hx2Mesh", fontsize=14)
ax2.set_title("Hx4Mesh", fontsize=14)
ax11.patch.set_linewidth('1') 
ax11.patch.set_edgecolor('black') 
ax22.patch.set_linewidth('1') 
ax22.patch.set_edgecolor('black') 

#sns.despine(bottom = True, left = True)
fig.suptitle('Relative Cost Savings (Communication Overhead)')


plt.legend([],[], frameon=False)
ax11.legend_.remove()
ax22.legend_.remove()
circ1 = mpatches.Patch( facecolor=colors[0],alpha=1,label='FatTree N.B.')
circ2= mpatches.Patch( facecolor=colors[1],alpha=1,label='FatTree 75% B.')
circ3 = mpatches.Patch(facecolor=colors[2],alpha=1,label='Dragonfly')
circ4 = mpatches.Patch(facecolor=colors[3],alpha=1,label='2D Torus')
ax11.legend(handles = [circ1,circ2,circ3,circ4],ncol=2,)
plt.tight_layout()
Path(save_folder_pdf).mkdir(parents=True, exist_ok=True)
Path(save_folder_img).mkdir(parents=True, exist_ok=True)
file_name = datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
plt.savefig(Path(save_folder_img) / (str("RingAllReduce") + file_name))
plt.savefig(Path(save_folder_pdf) / (str("RingAllReduce") + file_name + ".pdf"))