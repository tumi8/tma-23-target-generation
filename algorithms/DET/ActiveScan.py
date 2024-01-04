#!/usr/bin/python3.6
# encoding:utf-8
import subprocess, os,json, time
from AddrsToSeq import get_rawIP
from datetime import datetime

wc = lambda x: subprocess.check_output(["wc", "-l", x]).decode().split(" ")[0]
scan_counter = 0
now = int(datetime.now().timestamp())

def Scan(addr_set, source_ip, output_file, tid):
    """
    运用扫描工具检测addr_set地址集中的活跃地址

    Args：
        addr_set：待扫描的地址集合
        source_ip
        output_file
        tid:扫描的线程id

    Return：
        active_addrs：活跃地址集合
    """
    global scan_counter

    scan_input = output_file + f'/scan_input_{tid}_{now}_{scan_counter}.txt'
    scan_input_bl = output_file + f'/scan_input_{tid}_{now}_{scan_counter}.txt.bl'
    scan_input_apd = output_file + f'/scan_input_{tid}_{now}_{scan_counter}.txt.bl.apd'
    bl_file = 'zmap/ipv6-bl-merged.txt'
    apd_file = 'aliased-prefixes.txt'
    zmap_config = 'zmap/zmap.conf'
    scan_output = output_file + f'/scan_output_{tid}_{now}_{scan_counter}.txt'

    with open(scan_input, 'w', encoding = 'utf-8') as f:
        for addr in addr_set:
            f.write(addr + '\n')

    command_filter = ['grepcidr', '-v', '-f', f'{bl_file}', f'{scan_input}']
    with open(scan_input_bl, "w") as f:
        subprocess.run(command_filter, stdout=f)

    command_filter = ['grepcidr', '-v', '-f', f'{apd_file}', f'{scan_input_bl}']
    with open(scan_input_apd, "w") as f:
        subprocess.run(command_filter, stdout=f)

    active_addrs = set()
    command = 'zmap --config {} --ipv6-target-file={} -q -o {}'\
        .format(zmap_config, scan_input_apd, scan_output)
    print(command)
    
    print('[+] Scanning {} addresses...'.format(wc(scan_input_apd)))
    t_start = time.time()
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    
    while p.poll() == None:
        pass

    if p.poll() == 0:
        for line in open(scan_output):
            if line != '':
                active_addrs.add(line[0:len(line) - 1])
    else:
        raise Exception(f"command\n\n{command}\n\nreturned code {p.poll()}")
            
    print('[+] Over! Scanning duration:{} s'.format(time.time() - t_start))
    print('[+] {} active addresses detected!'
        .format(len(active_addrs)))
    return active_addrs



if __name__ == '__main__':
    addr_set = set()
    addr_set.add('2400:da00:2::29')
    addr_set.add('2404:0:8f82:a::201e')
    addr_set.add('2404:0:8e04:9::201e')
    addr_set.add('2001:4ca0:2001:13:250:56ff:feba:37ac')
    addr_set.add('2a10:3781:20::2')
    print(Scan(addr_set, "2001:4ca0:108:42::28", ".", 2))
