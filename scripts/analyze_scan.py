import argparse
import subprocess
import os, glob, csv
import multiprocessing
import pyasn

parser = argparse.ArgumentParser()
parser.add_argument("--scanresults", nargs="+")
parser.add_argument("--gendirs", nargs="+")
parser.add_argument("--scanfile", type=str)
parser.add_argument("--tmpdir", type=str, default="/data/steger-work/tmp")
parser.add_argument("--asndb", type=str, default="/data/steger-work/asn.db")
parser.add_argument("--apdfile", type=str, default="/data/steger-work/aliased-prefixes.txt")
parser.add_argument("--num-workers", type=int, default=6, dest="num_workers")
args = parser.parse_args()

asndb = pyasn.pyasn(args.asndb)

# Static values
WORKERS=args.num_workers
TMPDIR=args.tmpdir

# Paths for candidate sets of algorithms
genpaths = {
    "6Hit": "6Hit/candidates*",
    "6Scan": "6Scan/candidates*",
    "6Tree": "6Tree/targets_combined.txt",
    "DET": "DET/scan_input_combined.txt",
    "6Forest": "6Forest/results*",
    "6GAN": "6GAN/candidates_combined.txt",
    "6GCVAE": "6GCVAE/results*",
    "6Graph": "6Graph/results*",
    "6VecLM": "6VecLM/results*",
    "Entropy": "Entropy/results*",
}


###
# Asynchroneous worker funktions
###


# Takes tuple of input, pattern and output file and filters the input
# file for the patterns in the pattern file, saving the output to the output file
def work_grepcidr(files):
    fn_input, fn_patterns, fn_output = files
    if not os.path.isfile(fn_output):
        print("Filtering", fn_input, fn_output)
        subprocess.run(f"grepcidr -v -f {fn_patterns} {fn_input} > {fn_output}", shell=True, check=True)


# Takes tuple of input and output file and takes only the first column of a
# comma-separated CSV file, writing to the output file
def work_strip(files):
    fn_input, fn_output = files
    if not os.path.isfile(fn_output):
        print("Stripping", fn_input, fn_output)
        subprocess.run(f"cat {fn_input} | cut -d , -f 1 > {fn_output}", shell=True, check=True)

# Takes tuple of input and output file and converts all IPv6 addresses in
# the input file and converts them to long form, writing to output file
def work_explode_sort(files):
    fn_input, fn_output = files
    if not os.path.isfile(fn_output):
        print("Exploding", fn_input, fn_output)
        subprocess.run(f"ipv6exploder {fn_input} | sort -u > {fn_output}", shell=True, check=True)


# Takes tuple of input and output file, sorts input file to output file
def work_sort(files):
    fn_input, fn_output = files
    if not os.path.isfile(fn_output):
        print("Sorting", fn_input, fn_output)
        subprocess.run(f"sort -u {fn_input} > {fn_output}", shell=True, check=True)


# Takes tuple of two input files and output file, writes all lines found in
# both input files to output file, i.e. computs the intersection
def work_comm(files):
    fn_input1, fn_input2, fn_output = files
    if not os.path.isfile(fn_output):
        cmd = f"comm -12 {fn_input1} {fn_input2} > {fn_output}"
        print("Executing", cmd)
        return subprocess.check_output(cmd, shell=True)

# Takes tuple of two input files and output file, writes all lines found only
# in input file to output file
def work_comm_23(files):
    fn_input1, fn_input2, fn_output = files
    if not os.path.isfile(fn_output):
        cmd = f"comm -23 {fn_input1} {fn_input2} > {fn_output}"
        print("Executing", cmd)
        return subprocess.check_output(cmd, shell=True)

# Result files processing
# [result file] -> strip -> [result file].iponly
# [result file].iponly > static APD filter -> [result file].iponly.apd
# [result file].iponly.apd -> sort -> [result file].iponly.apd.sortu
protos = []
scan_res_files = dict()
cmds_res_strip = []
cmds_res_sort = []
cmds_res_apd = []
for fn_res in args.scanresults:
    # Extract protocol
    proto = fn_res.split(".")[-1]
    protos.append(proto)

    # File names
    fn_res_target = os.path.join(TMPDIR, os.path.basename(fn_res))
    fn_res_iponly = f"{fn_res_target}.iponly"
    fn_res_apd = f"{fn_res_iponly}.apd"
    fn_res_sorted = f"{fn_res_apd}.sortu"
    scan_res_files[proto] = fn_res_sorted

    # Commands
    cmds_res_strip.append((fn_res, fn_res_iponly))
    cmds_res_apd.append((fn_res_iponly, args.apdfile, fn_res_apd))
    cmds_res_sort.append((fn_res_apd, fn_res_sorted))

# Scanfile processing
scanfile_nonaliased = f"{args.scanfile}"
scanfile_nonaliased_nonaliased = os.path.join(TMPDIR, f"{os.path.basename(scanfile_nonaliased)}.apd")
scanfile_nonaliased_sorted = f"{scanfile_nonaliased_nonaliased}.sortu"

with multiprocessing.Pool(WORKERS) as p:
    res = p.map(work_grepcidr, [(scanfile_nonaliased, args.apdfile, scanfile_nonaliased_nonaliased)])
    res = p.map(work_sort, [(scanfile_nonaliased_nonaliased, scanfile_nonaliased_sorted)])


# Candidate and seed files processing
# [candidate file] -> sort -> [candidate file].sortu
# [seed file] -> sort -> [seed file].sortu
# [candidate file].sortu -> intersection with [seed file].sortu -> [candidate file].sortu.noseed
# [candidate file].sortu.noseed -> intersection with [scan file].apd.sortu -> [candidate file].sortu.noseed.apd
# In summary, sorts candidate sets and removes all addresses which were already found in the seed set
algos = list(genpaths.keys())
cats = set()
files_candidates = dict()
files_candidates_noseed = dict()
files_candidates_noseed_apd = dict()
files_seeds = dict()
cmds_seed_sort = []
cmds_candidate_sort = []
cmds_candidate_seed_overlap = []
cmds_candidate_apd_overlap = []
for algo in genpaths:
    files_candidates[algo] = dict()
    files_candidates_noseed[algo] = dict()
    files_candidates_noseed_apd[algo] = dict()
    for gendir in args.gendirs:
        for fn_candidate in glob.glob(f"{gendir}/generation*/results/{genpaths[algo]}"):
            # Extract category
            cat_str = list(filter(lambda x: "generation_" in x, fn_candidate.split("/")))
            if len(cat_str) > 1:
                print("More than one file", cat_str)
            else:
                cat = cat_str[0].split("_")[2] if len(cat_str[0].split("_")) > 2 else "Full"
            cats.add(cat)
            
            # Process seed file
            seed_file = os.path.join(gendir, cat_str[0], "seeds/responsive-addresses.txt")
            seed_file_sorted = os.path.join(TMPDIR, f"responsive-addresses_{cat}.txt")
            if not cat in files_seeds:
                files_seeds[cat] = seed_file_sorted
                cmds_seed_sort.append((seed_file, seed_file_sorted))
            
            # Process candidate file
            fn_candidate_sorted = os.path.join(TMPDIR, f"candidates_{algo}_{cat}.txt.sortu")
            fn_candidate_sorted_noseed = f"{fn_candidate_sorted}.noseed"
            fn_candidate_sorted_noseed_apd = f"{fn_candidate_sorted_noseed}.apd"
            files_candidates[algo][cat] = fn_candidate_sorted
            files_candidates_noseed[algo][cat] = fn_candidate_sorted_noseed
            files_candidates_noseed_apd[algo][cat] = fn_candidate_sorted_noseed_apd
            cmds_candidate_sort.append((fn_candidate, fn_candidate_sorted))
            cmds_candidate_seed_overlap.append((fn_candidate_sorted, seed_file_sorted, fn_candidate_sorted_noseed))
            cmds_candidate_apd_overlap.append((fn_candidate_sorted_noseed, scanfile_nonaliased_sorted, fn_candidate_sorted_noseed_apd))

with multiprocessing.Pool(WORKERS) as p:
    res = p.map(work_strip, cmds_res_strip)
    res = p.map(work_grepcidr, cmds_res_apd)
    res = p.map(work_explode_sort, cmds_res_sort)
    res = p.map(work_explode_sort, cmds_seed_sort)
    res = p.map(work_explode_sort, cmds_candidate_sort)
    res = p.map(work_comm_23, cmds_candidate_seed_overlap)
    res = p.map(work_comm, cmds_candidate_apd_overlap)


# Candidate result overlap
# Computs the responsive subsets of the candidate sets
cmds_comm = []
files_candidates_responsive = dict()
for proto in protos:
    files_candidates_responsive[proto] = dict()
    for algo in algos:
        files_candidates_responsive[proto][algo] = dict()
        for cat in cats:
            comm_out = os.path.join(TMPDIR, f"results_{algo}_{cat}_{proto}.txt")
            try:
                candidate_file = files_candidates_noseed_apd[algo][cat]
            except KeyError:
                # Create missing combination
                candidate_file = os.path.join(TMPDIR, f"candidates_{algo}_{cat}.txt.sortu")
                candidate_file_noseed = f"{candidate_file}.noseed"
                candidate_file_noseed_apd = f"{candidate_file_noseed}.apd"
                files_candidates[algo][cat] = candidate_file
                files_candidates_noseed[algo][cat] = candidate_file_noseed
                files_candidates_noseed_apd[algo][cat] = candidate_file_noseed_apd
                open(candidate_file, "w").close()
                open(candidate_file_noseed, "w").close()
                open(candidate_file_noseed_apd, "w").close()
                candidate_file = candidate_file_noseed_apd

            scan_res_file = scan_res_files[proto]
            files_candidates_responsive[proto][algo][cat] = comm_out
            cmds_comm.append((scan_res_file, candidate_file, comm_out))

with multiprocessing.Pool(WORKERS) as p:
    res = p.map(work_comm, cmds_comm)

def append_as_info(fn):
    fn_target = f"{fn}.ases"
    if os.path.isfile(fn_target):
        return 
    
    print("Analysing ASes for", fn)
    asn_data = dict()
    with open(fn) as f:
        for line in f:
            try:
                ip = line.strip()
                asn, _ = asndb.lookup(ip)
            except:
                continue
            if not asn in asn_data:
                asn_data[asn] = 0
            asn_data[asn] += 1
    
    with open(fn_target, "w") as fw:
        for asn, val in sorted(asn_data.items(), key=lambda x: x[1], reverse=True):
            fw.write(f"{asn},{val}\n")

# Analyzes the ASes found in the different candidate sets and responsive subsets
# Write the AS and frequency to a separate file
cmds_asinfo = []
for algo in algos:
    for cat in cats:
        cmds_asinfo.append(files_candidates_noseed_apd[algo][cat])
        for proto in protos:
            cmds_asinfo.append(files_candidates_responsive[proto][algo][cat])

for cat in cats:
    cmds_asinfo.append(files_seeds[cat])

with multiprocessing.Pool(WORKERS) as p:
    res = p.map(append_as_info, cmds_asinfo)