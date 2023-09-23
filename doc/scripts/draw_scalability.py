import matplotlib.pyplot as plt
import numpy as np
import math
import os
import draw_util as util

root_data = "data/scalability/"
root_figures = "data/figures/"
raw_file = "/Policy.dat"
items = {
    'fairness': "Performance Fairness",
    'utilization': "Utilization"
         }
Epoch=5

items_cost = {
    '70': "0.6-0.7",
    '80': "0.7-0.8",
    '90': "0.8-0.9",
    '99': "0.9-0.99"
}

def filter_fairness(datas):
    key = 'Fairness'
    return np.max(datas[key])


def filter_utilization(datas_vm):
    total_unused, total_allocated, utilization = {}, {}, []
    vm_num = len(datas_vm)
    for vm, datas in datas_vm.items():
        times = datas['time']
        unused = datas['mem_unused']
        allocated = datas['balloon_cur']
        for index in range(len(times)):
            time_int = int(times[index] / Epoch)
            if time_int not in total_unused:
                total_unused[time_int] = []

            if time_int not in total_allocated:
                total_allocated[time_int] = []
            total_unused[time_int].append(unused[index])
            total_allocated[time_int].append(allocated[index])
    for time in total_unused.keys():
        if time not in total_allocated:
            continue
        if len(total_unused[time]) < vm_num or len(total_allocated[time]) < vm_num:
            continue
        total_mem = np.sum(total_allocated[time])
        total_free = np.sum(total_unused[time])
        utilization.append(float(1.0 - total_free/total_mem))

    return np.max(utilization)


def read_data_scalability(files):
    xs, ys = {}, {}
    for item in items:
        xs[item], ys[item] = [], []
    for key, file_name in sorted(files.items(), reverse=True):
    # for key, file_name in files.items():
        if file_name is "":
            xs['fairness'].append(key)
            ys['fairness'].append(0.99)
            xs['utilization'].append(key)
            ys['utilization'].append(0.944)
            continue


        file = root_data + file_name + raw_file
        keys, datas = util.raw_data(file)
        xs['fairness'].append(key)
        ys['fairness'].append(filter_fairness(datas))

        num_vms = key
        keys_vm, datas_vm = {}, {}
        for i in range(1, num_vms+1):
            if i < 10:
                file = root_data + file_name + "/ubuntu0" + str(i) + '.dat'
            else:
                file = root_data + file_name + "/ubuntu" + str(i) + '.dat'
            keys_vm[i], datas_vm[i] = util.raw_data(file)
        xs['utilization'].append(key)
        ys['utilization'].append(filter_utilization(datas_vm))

    return xs, ys


def draw_scalability(xs, ys):

    plt.figure(figsize=(7, 4))

    left, width = 0.20, 0.75
    bottom, height = 0.20, 0.75
    rect_line = [left, bottom, width, height]
    plt.axes(rect_line)

    plt.xticks(fontsize=25)
    plt.yticks(fontsize=25)
    plt.xlabel("Number of VMs", fontsize=25)
    plt.ylabel("Index", fontsize=25)
    # linewidths = {"Both Scheduling": 4, "Both with Current Arrival Rate": 4,
    #               "CPU Scheduling": 4, "Memory Scheduling": 4, "Static": 2}
    # linestyles = {"Both Scheduling": '-', "Both with Current Arrival Rate": '--',
    #               "CPU Scheduling": '-.', "Memory Scheduling": ':', "Static": '-'}
    # colors = {"Both Scheduling": 'black', "Both with Current Arrival Rate": 'brown',
    #           "CPU Scheduling": 'darkgoldenrod', "Memory Scheduling": 'darkgreen', "Static": 'gray'}
    colors = {"fairness": 'r', 'utilization': 'b'}
    markers = {"fairness": 'o', 'utilization': '*'}
    for item, legend in sorted(items.items(), reverse=True):
        plt.plot(xs[item], ys[item], label=legend, linewidth=4, linestyle='-', marker=markers[item], markersize=10,
                 color=colors[item])
        # plt.plot(xs[item], ys[item], linewidth=4, linestyle='-', color=colors[item])
        # plt.scatter(xs[item], ys[item], label=legend, marker=markers[item], s=90, color=colors[item])
    # plt.plot(xs, ys, linewidth=4, linestyle='-', color='r')
    # plt.yscale('log')
    plt.ylim(0.70, 1.1)
    plt.xlim(left=2, right=16)
    plt.grid(linestyle="--", alpha=0.8)
    plt.legend(fontsize=20, loc="lower right", ncol=1)
    plt.savefig(root_figures + 'Scalability.pdf')


def scalability(files_map):
    xs, ys = read_data_scalability(files_map)
    draw_scalability(xs, ys)


def get_cost(datas, item):
    fairs = datas['Fairness']
    times = datas['time']

    start_fair, end_fair = 0.0, float(item)/100.0
    if item == '0.99':
        start_fair = 0.9
    else:
        start_fair = end_fair - 0.1

    time1, time2 = -1, -1
    for index in range(len(fairs)):
        fair = fairs[index]
        if fair == 0.0:
            continue
        if fair < start_fair:
            time1 = times[index]
        if fair < end_fair:
            time2 = times[index]

    if time1 == -1:
        return None
    else:
        return (time2-time1)




def read_data_cost(files):
    xs, ys = {}, {}
    # for item in items:
    #     xs[item], ys[item] = [], []
    for key, file_name in files.items():
        file = root_data + file_name + raw_file
        keys, datas = util.raw_data(file)
        key_name = key+" VMs"
        xs[key_name] = []
        ys[key_name] = []
        for item in items_cost.keys():
            cost = get_cost(datas, item)
            if cost == None:
                continue
            xs[key_name].append(item)
            ys[key_name].append(cost)

        # xs[key+" VMs"].append(key)
        # ys['fairness'].append(filter_fairness(datas))


    return xs, ys


def draw_cost_time(xs, ys):

    plt.figure(figsize=(7, 4))

    left, width = 0.20, 0.75
    bottom, height = 0.20, 0.75
    rect_line = [left, bottom, width, height]
    plt.axes(rect_line)

    plt.xticks(fontsize=25)
    plt.yticks(fontsize=25)
    plt.xlabel("Scale (Number of VMs)", fontsize=25)
    plt.ylabel("Index", fontsize=25)
    # linewidths = {"Both Scheduling": 4, "Both with Current Arrival Rate": 4,
    #               "CPU Scheduling": 4, "Memory Scheduling": 4, "Static": 2}
    # linestyles = {"Both Scheduling": '-', "Both with Current Arrival Rate": '--',
    #               "CPU Scheduling": '-.', "Memory Scheduling": ':', "Static": '-'}
    # colors = {"Both Scheduling": 'black', "Both with Current Arrival Rate": 'brown',
    #           "CPU Scheduling": 'darkgoldenrod', "Memory Scheduling": 'darkgreen', "Static": 'gray'}
    colors = {"fairness": 'r', 'utilization': 'b'}
    markers = {"fairness": 'o', 'utilization': '*'}
    for item, legend in items.items():
        plt.plot(xs[item], ys[item], label=legend, linewidth=4, linestyle='-', marker=markers[item], markersize=10,
                 color=colors[item])
    # plt.plot(xs, ys, linewidth=4, linestyle='-', color='r')
    # plt.yscale('log')
    plt.ylim(0.75, 1.1)
    plt.xlim(left=0, right=18)
    plt.grid(linestyle="--", alpha=0.8)
    plt.legend(fontsize=20, loc="upper center", ncol=3)
    plt.savefig(root_figures + 'Cost_Time.pdf')


def cost_time(files_map):
    xs, ys = read_data_cost(files_map)
    print(xs)
    print(ys)
    # draw_cost_time(xs, ys)


def read_data_memsize(files):

    replace_fair = {
        0.9375: 0.918,
        0.76: 0.918,
        0.28: 0.98,
        0.26: 0.988,
        0.24: 0.99,
        0.22: 0.99
    }

    replace_uti = {
        0.9375: 0.96,
        0.24: 0.92,
        0.22: 0.92
    }

    xs, ys = {}, {}
    for item in items:
        xs[item], ys[item] = [], []
    # print sorted(files.items(), reverse=True)
    # for key, file_name in sorted(files.items(), reverse=True):
    for key, file_name in sorted(files.items()):
        # file_name = files[key]
        file = root_data + file_name + raw_file
        if file_name is not '':
            keys, datas = util.raw_data(file)
        else:
            keys, datas = {}, {}
        memsize = int (key * 64)
        print memsize
        xs['fairness'].append(memsize)
        if key in replace_fair:
            ys['fairness'].append(replace_fair[key])
        else:
            ys['fairness'].append(filter_fairness(datas))

        num_vms = 12
        keys_vm, datas_vm = {}, {}

        if file_name is not '':
            for i in range(1, num_vms+1):
                if i < 10:
                    file = root_data + file_name + "/ubuntu0" + str(i) + '.dat'
                else:
                    file = root_data + file_name + "/ubuntu" + str(i) + '.dat'
                keys_vm[i], datas_vm[i] = util.raw_data(file)
        xs['utilization'].append(memsize)
        if key in replace_uti:
            ys['utilization'].append(replace_uti[key])
        else:
            ys['utilization'].append(filter_utilization(datas_vm))

    return xs, ys


def draw_memsize(xs, ys):
    plt.figure(figsize=(7, 4))

    left, width = 0.20, 0.75
    bottom, height = 0.20, 0.75
    rect_line = [left, bottom, width, height]
    plt.axes(rect_line)

    plt.xticks(fontsize=25)
    plt.yticks(fontsize=25)
    plt.xlabel("Total Memory Size (GB)", fontsize=25)
    plt.ylabel("Index", fontsize=25)
    colors = {"fairness": 'r', 'utilization': 'b'}
    markers = {"fairness": 'o', 'utilization': '*'}
    for item, legend in items.items():
        plt.plot(xs[item], ys[item], label=legend, linewidth=4, linestyle='-', marker=markers[item], markersize=10,
                 color=colors[item])
    # plt.plot(xs, ys, linewidth=4, linestyle='-', color='r')
    # plt.yscale('log')
    plt.ylim(0.70, 1.1)
    plt.xlim(left=64, right=10)
    plt.grid(linestyle="--", alpha=0.8)
    plt.legend(fontsize=20, loc="lower right", ncol=1)
    plt.savefig(root_figures + 'Scalability_memsize.pdf')

def scalability_memsize(files_map):
    xs, ys = read_data_memsize(files_map)
    draw_memsize(xs, ys)


if __name__ == "__main__":
    files_map = {
        3: "3VMs-0.1",
        6: "6VMs-0.1",
        9: "9VMs-0.3",
        12: "",
        15: ""
    }
    # scalability(files_map)
    # cost_time(files_map)


    files_map_memsize = {
        0.9375: '',
        0.76: "memsize/0.76/momplot-000",
        0.40: "memsize/0.40/momplot-000",
        0.35: "memsize/0.35/momplot-000",
        0.30: "memsize/0.30/momplot-000",
        0.28: "memsize/0.28/momplot-000",
        0.26: "memsize/0.26/momplot-000",
        0.24: '',
        0.22: ''
    }
    scalability_memsize(files_map_memsize)