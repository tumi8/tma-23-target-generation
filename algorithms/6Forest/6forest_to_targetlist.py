import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="generated_regions.txt")
parser.add_argument("--output", default="generated_addresses.txt")
args = parser.parse_args()

def seed_to_targets_distance(seed, indizes):
    # takes a seed address and replaces each wildcard with a hex digit from 0 to f each
    # returns all those permutations
    res = []
    for ind in indizes:
        res.extend([''.join([seed[:ind], hex(i)[2:], seed[ind + 1:], '\n']) for i in range(16)])
        # res += [seed[:ind] + hex(i)[2:] + seed[ind + 1:] for i in range(16)]
    return res

def seed_to_targets_plain(seed, indizes):
    # takes a seed address and replaces each wildcard with a hex digit from 0 to f each
    # returns all those permutations
    res = []
    if len(indizes) == 1:
        ind = indizes[0]
        res.extend([''.join([seed[:ind], hex(i)[2:], seed[ind + 1:], '\n']) for i in range(16)]) 
    else:
        for ind in indizes:
            # new_indizes are ones except the current one
            new_indizes = [i for i in indizes if i != ind]
            for i in range(16):
                res.extend(seed_to_targets_plain(''.join([seed[:ind], hex(i)[2:], seed[ind + 1:]]), new_indizes))
    return res

def pattern_to_indizes(pattern):
    # returns the indizes of every wildcard (*) of the pattern
    return list(filter(lambda x: pattern[x] == "*", range(len(pattern))))

partitioned = False
pattern_mode = False
run_path = __file__.split('6forest_to_tar')[0]
indizes = []
with open(args.input) as f, open(args.output, "w") as fw:
    for line in f:
        if "----" in line:
            partitioned = False
            pattern_mode = False
        
        if not partitioned:
            if line == "\n":
                partitioned = True
            continue
        else:
            if len(line) == 33:
                indizes = pattern_to_indizes(line.strip())
                if len(indizes) > 3:
                    pattern_mode = True
                else:          
                    pattern_mode = False
                    targets = seed_to_targets_plain(line.strip(), indizes)
                    for ip in targets:
                        ip = ":".join([ip[i:i + 4] for i in range(0, len(ip)-3, 4)]) + "\n"
                        fw.write(ip)
            
            elif len(line) in range(37, 39) and pattern_mode:
                trimmed_line = line[:32]
                targets = seed_to_targets_distance(trimmed_line, indizes)
                for ip in targets:
                    ip = ":".join([ip[i:i + 4] for i in range(0, len(ip)-3, 4)]) + "\n"
                    fw.write(ip)
