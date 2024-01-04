import ipaddress
import sys

def seed_to_targets(seed, indizes):
    # takes a seed address and replaces each wildcard with a hex digit from 0 to f each
    # returns all those permutations
    res = []
    for ind in indizes:
        res += [seed[:ind] + hex(i)[2:] + seed[ind + 1:] for i in range(16)]
    return res

def pattern_to_indizes(pattern):
    # returns the indizes of every wildcard (*) of the pattern
    return list(filter(lambda x: pattern[x] == "*", range(len(pattern))))

patternmode = True
for line in sys.stdin:
    if patternmode:
        if "--" in line:
            patternmode = False
            continue

        if not "p" in line:
            # finds the wilcard positions for this pattern
            indizes = pattern_to_indizes(line.strip())
    else:
        if line == "\n":
            patternmode = True
            continue

        # we find the seed addresses belonging to this pattern here
        # permutate them and output them in IPv6 form
        targets = seed_to_targets(line.strip(), indizes)
        for ip in targets:
            ip = ":".join([ip[i:i + 4] for i in range(0, len(ip), 4)])
            print(ip)
