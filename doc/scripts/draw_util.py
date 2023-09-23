

def read_keys(file):
    words = file.readline().split()
    if words[0] == '#':
        return words[1:-1]


def read_start(file):
    start = file.readline().split()[0]
    while start is '#':
        start = file.readline().split()[0]

    return float(start)


def raw_data(file_name):
    file = open(file_name)
    keys = read_keys(file)
    start_time = read_start(file)

    datas = {}
    for key in keys:
        datas[key] = []

    for line in file.readlines():
        line = line.strip('\n')
        words = line.split()

        if words[0] == '#':
            continue

        for index in range(len(keys)):
            word = words[index]
            key = keys[index]
            if word == 'None':
                word = '0'
            if key == 'VM':
                data = word
            else:
                data = float(word)

            if key == 'time':
                data -= start_time

            datas[keys[index]].append(data)

    return keys, datas
