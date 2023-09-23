#!/bin/bash

list="0.78 0.40 0.35 0.32 0.3 0.28 0.26"

conf_file="doc/mom-balloon.conf"
message_file="doc/message"

# Loop through the values in the list
for mem in $list; do
    # Modify the "doc/mom-conf.yaml" file with the current mem value
    sed -i '' "s/total-mem:.*/total-mem: $mem/" ${conf_file}
    python3 -c 'import time; time.sleep('"5"')'

    rm -rf "../data/test1/*"
    python3 -c 'import time; time.sleep('"5"')'

    # Step 1: Start the program
    python momd -c ${conf_file} &

    # Store the process ID (PID) of the program
    PID=$!
    echo ${PID}

    # Step 2: Check the "doc/message" file every ten minutes
    while true; do
        python3 -c 'import time; time.sleep('"600"')'

        # Read the contents of the "doc/message" file
        status=$(cat ${message_file})

        # Step 3: If the status is "completed"
        if [ "$status" == "completed" ]; then
            # Terminate the program
            kill $PID

            # 4. 创建目标文件夹并将文件移动到该文件夹中
            dest_dir="../data/scalability/$mem"
            data_file="../data/test1/momplot-000"
            rm -rf "$dest_dir"
            mkdir -p "$dest_dir"
            mv "$data_file" "$dest_dir"

            break  # Exit the inner loop and proceed to the next mem value
        fi
    done
done
