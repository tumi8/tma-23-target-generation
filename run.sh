#! /bin/bash

ROOTDIR="$(dirname "$(realpath "$0")")"
PATH="$PATH:$ROOTDIR/miniconda3/bin"

if [ -z "$2" ]
then
    RUNDIR="$ROOTDIR/generation_$(date -u "+%F-%H%M")"
    mkdir -p "$RUNDIR"
else
    RUNDIR=$2
fi

if [ -d "$ROOTDIR/miniconda3" ]
then
    eval "$(conda shell.bash hook)"
fi

SEEDDIR="$RUNDIR/seeds"
SEEDFULL="$(realpath "$SEEDDIR/responsive-addresses.txt")"
ALGDIR="$ROOTDIR/algorithms-$(date -u "+%F-%H%M%S")"
ALGDIRBASE="$ROOTDIR/algorithms"
RESDIR="$RUNDIR/results"
LOGDIR="$RUNDIR/logs"
mkdir -p "$RESDIR" "$LOGDIR" "$SEEDDIR"
cp -r "$ALGDIRBASE" "$ALGDIR"

log_start() {
    LOG="$1"
    touch "$LOG"
    {
        echo -e "------------------------------------------------------------" 
        echo -e "------------------------------------------------------------"
    } >> "$LOG"

    echo "Running $2..." | tee -a "$LOG"            
    {
        echo "Start time: $(date +%H:%M:%S@%Y.%m.%d)" 
        echo "Seed file: $SEEDFULL" 
        echo "Algorithm directory: $ALGDIR" 
        echo -e "$(hostnamectl)"
        echo -e "\n-----------------------Program Output-----------------------" 
    } >> "$LOG"
}

log_end() {
    LOG="$1"
    {   
        echo -e "---------------------End Program Output---------------------"
        echo -e "End time: $(date +%H:%M:%S@%Y.%m.%d)\n\n" 
    } >> "$LOG"
}

create_dirs() {
    GANDIR="$ALGDIR/6GAN/data"
    VECLMDIR="$ALGDIR/6VecLM/data"
    GCVAEDIR="$ALGDIR/6GCVAE/data"

    mkdir -p "$GANDIR/candidate_set"
    mkdir -p "$GANDIR/category_data/ec/id"
    mkdir -p "$GANDIR/category_data/ec/data"
    mkdir -p "$GANDIR/save_data"
    mkdir -p "$GANDIR/source_data"

    mkdir -p "$VECLMDIR/generation_data"
    mkdir -p "$VECLMDIR/processed_data"
    mkdir -p "$VECLMDIR/public_dataset"
    mkdir -p "$ALGDIR/6VecLM/models"

    mkdir -p "$GCVAEDIR/generated_data"
    mkdir -p "$GCVAEDIR/processed_data"
    mkdir -p "$GCVAEDIR/public_datasets"
}

install_dependencies_apt() {
    apt-get update -y
    apt-get install build-essential \
        cmake libgmp3-dev gengetopt \
        libpcap-dev flex byacc libjson-c-dev \
        pkg-config libunistring-dev \
        autoconf libcurl4-openssl-dev \
        libjsoncpp-dev zlib1g-dev \
        tree screen nvtop -y
    apt-get install nvidia-cuda-toolkit -y
    
    pip uninstall pip -y
    
    # install miniconda
    if [ ! -d "$ROOTDIR/miniconda3" ]; then
        echo "Installing miniconda..."
        wget -P "$ROOTDIR" https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
        bash "$ROOTDIR/Miniconda3-latest-Linux-x86_64.sh" -b -p "$ROOTDIR"/miniconda3
        rm "$ROOTDIR/Miniconda3-latest-Linux-x86_64.sh"
        eval "$(conda shell.bash hook)"
    else
        echo "Miniconda already installed. Skipping installation."
    fi
}

install_dependencies_pip() {
    #Utils
    conda create -n utils python=3.9 -y
    conda activate utils
    pip install pyasn
    conda deactivate

    #6GAN
    conda create -n 6gan python=3.6 -y
    conda activate 6gan
    pip install scikit-learn
    pip install tensorflow-gpu==1.15.5 pandas gensim==3.8.3 numpy ipaddress
    pip install protobuf==3.12.2
    conda install cudatoolkit=10.0 -y
    conda install cudnn=7.6.5 -y
    conda deactivate

    #6GCVAE
    conda create -n 6gcvae python=3.6 -y
    conda activate 6gcvae
    pip install scikit-learn
    pip install numpy==1.19.2
    pip install tensorflow-gpu==1.15.5 keras==2.2.4
    conda deactivate

    #6Forest
    conda create -n 6forest python=3.7 -y
    conda activate 6forest
    pip install IPy numpy==1.21.2
    conda deactivate

    #6Graph
    conda create -n 6graph python=3.7 -y
    conda activate 6graph
    pip install IPy numpy==1.21.2 networkx
    conda deactivate

    #6VecLM
    conda create -n 6veclm python=3.7 -y
    conda activate 6veclm
    pip install torch==1.3.1 torchvision torchaudio gensim==3.6.0 scikit-learn torchsummary matplotlib seaborn
    conda deactivate

    # EntropyIP
    conda create -n entropy-ip python=2.7 -y
    conda activate entropy-ip
    pip install matplotlib scikit-learn
    pip install bnfinder toposort==1.7
    conda deactivate
}

install_dependencies_other() {
    GANDIR="$ALGDIR/6GAN"
    ECDIR="$GANDIR/Tools/entropy-clustering"
    
    # 6GAN$GANDIR/Tools/entropy-clustering
    if [ ! -d "$GANDIR/Tools" ]; then
        mkdir -p "$GANDIR/Tools"

        git clone https://github.com/fgont/ipv6toolkit.git "$GANDIR/Tools/ipv6toolkit"

        make -C "$GANDIR/Tools/ipv6toolkit" all
        make -C "$GANDIR/Tools/ipv6toolkit" install

        git clone https://github.com/pforemski/entropy-clustering.git "$ECDIR"

        curl -L -o "$ECDIR/go1.19.3.linux-amd64.tar.gz" https://go.dev/dl/go1.19.3.linux-amd64.tar.gz -k
        rm -rf /usr/local/go
        tar -C /usr/local -xzf "$ECDIR/go1.19.3.linux-amd64.tar.gz"
        export PATH=$PATH:/usr/local/go/bin
        
        env -C "$ECDIR" go mod init entropy-clustering      # This is required
        env -C "$ECDIR" go get github.com/pforemski/gouda/...
        env -C "$ECDIR" go get github.com/fatih/color
        
        env -C "$ECDIR" make
    fi

    #6Tree
    g++ -std=c++11 "$ALGDIR"/6tree/*.cpp -o "$ALGDIR"/6tree/6tree

    #6Scan
    env -C "$ALGDIR/6Scan" ./bootstrap
    env -C "$ALGDIR/6Scan" ./configure
    make -C "$ALGDIR/6Scan"
}

setup() {
    ALGDIR2="$ALGDIR"
    ALGDIR="$ALGDIRBASE"
    install_dependencies_apt
    install_dependencies_pip
    install_dependencies_other
    create_dirs
    ALGDIR="$ALGDIR2"
}

run_6gcvae(){
    GCVAEDIR="$ALGDIR/6GCVAE"
    LOG="$LOGDIR/6GCVAE.log"
    log_start "$LOG" "6GCVAE"

    cp "$SEEDFULL" "$GCVAEDIR/data/public_datasets/responsive-addresses.txt"

    # Run 6GCVAE
    conda activate 6gcvae
    echo -e "\nRunning data_process.py" | tee -a "$LOG"
    env -C "$GCVAEDIR" python "data_process.py" --input "$SEEDFULL" 2>&1 | tee -a "$LOG"
    echo -e "\nRunning gcnn_vae.py"  | tee -a "$LOG"
    env -C "$GCVAEDIR" python "gcnn_vae.py" "$GCVAEDIR" 2>&1 | tee -a "$LOG"
    echo -e "\nRunning generation.py" | tee -a "$LOG"
    env -C "$GCVAEDIR" python "generation.py" "$GCVAEDIR" 2>&1 | tee -a "$LOG"
    conda deactivate
    
    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/6GCVAE"
    
    # Store result with timestamped filename
    cp "$GCVAEDIR/data/generated_data/6gcvae_generation.txt" "$RESDIR/6GCVAE/results_6gcvae_$(date +%Y%m%d_%H%M%S).txt"
}

run_6tree() {
    TREEDIR="$ALGDIR/6tree"
    LOG="$LOGDIR/6Tree.log" 
    log_start "$LOG" "6Tree"

    cp "/root/scan-meta/release/ipv6-bl-merged.txt" "$TREEDIR"
    cp "$SEEDDIR/aliased-prefixes.txt" "$TREEDIR"
    
    # Data translation
    env -C "$TREEDIR" ./6tree -T -in-std "$SEEDFULL" -out-b4 "seeds_hex" 2>&1 | tee -a "$LOG"
    # Space tree generation
    mkdir -p "$TREEDIR/tree_hex"
    env -C "$TREEDIR" ./6tree -G -in-b4 "seeds_hex" -out-tree "tree_hex" 2>&1 | tee -a "$LOG"
    # Global search
    env -C "$TREEDIR" ./6tree -R -in-tree "tree_hex" -out-res "result_hex" 2>&1 | tee -a "$LOG"
    
    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/6Tree"
    
    cp "$TREEDIR"/targets*_*.txt "$RESIDR/6Tree"
    cp "$TREEDIR/result_hex/discovered_addrs" "$RESDIR/6Tree/results_6tree_$(date +%Y%m%d_%H%M%S).txt"
}

run_6gan() {
    GANDIR="$ALGDIR/6GAN"
    TOOLS_EC="$GANDIR/Tools/entropy-clustering"
    DATA_EC="$GANDIR/data/save_data"
    GANRES="$RESDIR/6GAN/$(date +%Y%m%d_%H%M%S)/"
    LOG="$LOGDIR/6GAN.log"
    log_start "$LOG" "6GAN"
    
    cp "$SEEDFULL" "$GANDIR/data/source_data/responsive-addresses.txt"
    cp "$SEEDDIR/aliased-prefixes.txt" "$GANDIR/data/source_data/aliased-prefixes.txt"

    # run it
    conda activate 6gan
    cat "$SEEDFULL" | "$TOOLS_EC/ipv6-addr2hex" | "$TOOLS_EC/profiles" > "$DATA_EC/ec_profile.txt"
    cat "$DATA_EC/ec_profile.txt" | "$TOOLS_EC/clusters" -kmeans -k 6 > "$DATA_EC/ec_cluster.txt"

    env -C "$GANDIR" python "$GANDIR/train.py" 2>&1 | tee -a "$LOG"
    conda deactivate
    
    # Extract results
    log_end "$LOG"
    mkdir -p "$GANRES"
    cp -r "$GANDIR/data/candidate_set"/candidate* "$GANRES"
}

run_6forest() {
    FORESTDIR="$ALGDIR/6Forest"
    LOG="$LOGDIR/6Forest.log"
    log_start "$LOG" "6Forest"
    
    cp "$SEEDFULL" "$FORESTDIR/seeds"

    # run 6Forest
    conda activate 6forest
    echo -e "\nRunning convert.py" | tee -a "$LOG"
    env -C "$FORESTDIR" python "convert.py" "$SEEDFULL" | tee -a "$LOG"
    echo -e "\nRunning main.py" | tee -a "$LOG"
    env -C "$FORESTDIR" python "main.py" > "$FORESTDIR/generated_regions.txt" 2>&1 | tee -a "$LOG"
    conda deactivate
        
    # Interpret results
    python "$FORESTDIR/6forest_to_targetlist.py" --input "$FORESTDIR/generated_regions.txt" --output "$FORESTDIR/generated_addresses.txt"  2>&1 | tee -a "$LOG"

    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/6Forest"
    cp "$FORESTDIR/generated_regions.txt" "$RESDIR/6Forest/regions_6forest_$(date +%Y%m%d_%H%M%S).txt"
    cp "$FORESTDIR/generated_addresses.txt" "$RESDIR/6Forest/results_6forest_$(date +%Y%m%d_%H%M%S).txt"
}

run_6graph() {
    GRAPHDIR="$ALGDIR/6Graph"
    LOG="$LOGDIR/6Graph.log"
    log_start "$LOG" "6Graph"

    cp "$SEEDFULL" "$GRAPHDIR/seeds"

    conda activate 6graph
    echo -e "\nRunning convert.py" | tee -a "$LOG"
    env -C "$GRAPHDIR" python "convert.py" "$SEEDFULL" 2>&1 | tee -a "$LOG"
    echo -e "\nRunning main.py" | tee -a "$LOG"
    env -C "$GRAPHDIR" python "main.py" | tee -a "$LOG" | python "$GRAPHDIR/6graph_to_targetlist.py" > "$GRAPHDIR/generated_addresses.txt" 2>&1 | tee -a "$LOG"
    conda deactivate

    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/6Graph"
    cp "$GRAPHDIR/generated_addresses.txt" "$RESDIR/6Graph/results_6graph_$(date +%Y%m%d_%H%M%S).txt"
}

run_6veclm() {
    VECLMDIR="$ALGDIR/6VecLM"
    LOG="$LOGDIR/6VecLM.log"
    log_start "$LOG" "6VecLM"
        
    conda activate 6veclm

    echo -e "\nRunning data_processing.py" | tee -a "$LOG"
    env -C "$VECLMDIR" python "data_processing.py" --input "$SEEDFULL" 2>&1 | tee -a "$LOG"

    echo -e "\nRunning ipv62vec.py" | tee -a "$LOG"
    env -C "$VECLMDIR" python "ipv62vec.py" 2>&1 | tee -a "$LOG"

    echo -e "\nRunning ipv6_transformer.py" | tee -a "$LOG"
    # python "$VECLMDIR/ipv6_transformer.py" > "$VECLMDIR/generated_predicted_addresses.txt" 2>&1 | tee -a "$LOG"
    env -C "$VECLMDIR" python "ipv6_transformer.py" 2>&1 | tee -a "$LOG"
    
    echo -e "\nRunning model_load.py" | tee -a "$LOG"
    env -C "$VECLMDIR" python "model_load.py" 2>&1 | tee -a "$LOG"

    conda deactivate
    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/6VecLM" 
    cp "$VECLMDIR/data/generation_data/candidates.txt" "$RESDIR/6VecLM/results_6veclm_$(date +%Y%m%d_%H%M%S).txt"

    conda deactivate
}

run_entropy() { 
    ENTROPYDIR="$ALGDIR/entropy-ip"
    LOG="$LOGDIR/Entropy.log" 
    log_start "$LOG" "Entropy"
    
    conda activate entropy-ip
    chmod +x "$ENTROPYDIR"/ALL.sh "$ENTROPYDIR"/a4-bayes-prepare.sh "$ENTROPYDIR"/a5-bayes.sh "$ENTROPYDIR"/b1-webreport.sh 2>&1 | tee -a "$LOG"
    find "$ENTROPYDIR"/ -name "*.py" -exec chmod +x {} \;       # may have problem

    "$ALGDIR"/6tree/6tree -T -in-std "$SEEDFULL" -out-b4 "$SEEDDIR"/hex_seeds 2>&1 | tee -a "$LOG"
    "$ENTROPYDIR"/ALL.sh "$SEEDDIR"/hex_seeds "$ENTROPYDIR" 2>&1 | tee -a "$LOG"
    python2 "$ENTROPYDIR"/c1-gen.py "$ENTROPYDIR"/out/cpd -n 10000000 > "$ENTROPYDIR"/out/reduced 2>&1 | tee -a "$LOG"
    python2 "$ENTROPYDIR"/c2-decode.py "$ENTROPYDIR"/out/reduced "$ENTROPYDIR"/out/analysis > "$ENTROPYDIR"/out/hex_results 2>&1 | tee -a "$LOG"
    conda deactivate

    "$ALGDIR"/6tree/6tree -T -in-b4 "$ENTROPYDIR"/out/hex_results -out-std "$ENTROPYDIR"/out/std_results 2>&1 | tee -a "$LOG"
    
    # Extract results
    log_end "$LOG"
    mkdir -p "$RESDIR/Entropy"
    cp "$ENTROPYDIR"/out/std_results "$RESDIR/Entropy/results_entropyip_$(date +%Y%m%d_%H%M%S).txt"
}

combine () {
    cd "$1"
    ls -1 | grep "candidate_" | xargs cat >> "$RESDIR/$2/candidates_$(date +%Y%m%d_%H%M%S).txt"
    cd -
}

wrap_6scan() {
    EXECDIR="$ALGDIR/6Scan"
    LOG="$LOGDIR/$1.log"
    log_start "$LOG" "$1"

    # install iptables blocklist filter
    "$ROOTDIR/bl_iptables.sh" "/root/scan-meta/release/ipv6-bl-merged.txt"

    # run scan
    cp "$SEEDFULL" "$EXECDIR/seeds.txt"
    env -C "$EXECDIR" "./6scan" -t "ICMP6" -I eno3 -s "$1" -F "seeds.txt" -r 1 -b 10 --srcmac "40:a8:f0:1e:9c:4a" --dstmac "00:1c:73:00:00:99" | tee -a "$LOG"

    # remove iptables filter
    "$ROOTDIR/rm_iptables.sh"

    mkdir -p "$RESDIR/$1"
    combine "$EXECDIR" "$1"
    cp "$EXECDIR/output/"* "$RESDIR/$1"

    log_end "$LOG"
}

run_6scan() {
    wrap_6scan "6Scan"
}

run_6hit() {
    wrap_6scan "6Hit"
}

run_DET() {
    EXECDIR="$ALGDIR/DET"
    LOG="$LOGDIR/DET.log"
    log_start "$LOG" "DET"
    mkdir -p "$EXECDIR/output"
    cp "$SEEDDIR/aliased-prefixes.txt" "$EXECDIR"

    env -C "$EXECDIR" python3 "DynamicScan.py" --input "$SEEDFULL" --output "output" --budget 10000000 --IPv6="2001:4ca0:108:42::1:28" 2>&1 | tee -a "$LOG"

    mkdir -p "$RESDIR/DET"
    cp "$EXECDIR"/output/scan_input* "$RESDIR/DET"
    cp "$EXECDIR"/output/scan_output* "$RESDIR/DET"
    log_end "$LOG"
}

categorize_data() {
    CATS=("Educational/Research" "Non-Profit" "Content" "Cable/DSL/ISP" "NSP")
    CATNAMES=("Educational" "Non-Profit" "Content" "ISP" "NSP")

    conda activate utils
    for i in $(seq 0 $((${#CATS[@]} - 1)))
    do
        CATEG_DIR="$RUNDIR"_"${CATNAMES[i]}"
        mkdir -p "$CATEG_DIR"
        cp -r "$SEEDDIR" "$CATEG_DIR"
        python3 filter_cat.py --input "$SEEDFULL" --asn-db "$SEEDDIR/asn.db" --peeringdb "$SEEDDIR/peeringdb.json" --category "${CATS[i]}"  > "$CATEG_DIR/seeds/responsive-addresses.txt"
    done
    conda deactivate
}

download_data() {
    rm -r "${SEEDDIR:?}/*" > /dev/null 2>&1
    
    curl -L -o "$SEEDDIR"/responsive-addresses.txt.xz https://alcatraz.net.in.tum.de/ipv6-hitlist-service/open/responsive-addresses.txt.xz -k
    curl -L -o "$SEEDDIR"/aliased-prefixes.txt.xz https://alcatraz.net.in.tum.de/ipv6-hitlist-service/open/aliased-prefixes.txt.xz -k 
    curl -L -o "$SEEDDIR"/non-aliased-prefixes.txt.xz https://alcatraz.net.in.tum.de/ipv6-hitlist-service/open/non-aliased-prefixes.txt.xz -k

    curl -L -o "$SEEDDIR"/peeringdb.json "https://publicdata.caida.org/datasets/peeringdb/$(date -d yesterday +%Y)/$(date -d yesterday +%m)/peeringdb_2_dump_$(date -d yesterday +%Y_%m_%d).json"

    conda activate utils
    env -C "$SEEDDIR" pyasn_util_download.py --latestv46
    env -C "$SEEDDIR" pyasn_util_convert.py --single "$(basename "$SEEDDIR"/rib*.bz2)" asn.db
    rm "$SEEDDIR"/rib*
    conda deactivate
    
    unxz "$SEEDDIR"/responsive-addresses.txt.xz "$SEEDDIR"/aliased-prefixes.txt.xz "$SEEDDIR"/non-aliased-prefixes.txt.xz
    cp "$SEEDDIR"/responsive-addresses.txt "$SEEDDIR"/responsive-addresses-backup.txt
    for i in {0..100}; do cat "$ROOTDIR"/seed.txt >> "$ROOTDIR"/rand.txt; done
    tail -n +2 "$SEEDDIR"/responsive-addresses-backup.txt | shuf --random-source "$ROOTDIR"/rand.txt > "$SEEDDIR"/responsive-addresses.txt
}

run_all() {
    run_6forest & run_6gan & run_6gcvae & run_6graph & run_6veclm & run_entropy
    wait
}

case $1 in
    "SETUP")
        setup
        ;;
    "DOWNLOAD")
        download_data
        ;;
    "6GCVAE")
        run_6gcvae
        ;;
    "6TREE")
        run_6tree
        ;;
    "6GAN")
        run_6gan
        ;;
    "6FOREST")
        run_6forest
        ;;
    "6GRAPH")
        run_6graph
        ;;
    "6VECLM")
        run_6veclm
        ;;
    "DET")
        run_DET
        ;;
    "6Scan")
        run_6scan
        ;;
    "6Hit")
        run_6hit
        ;;
    "ENTROPY")
        run_entropy
        ;;
    "CATEGORIZE")
        categorize_data
        ;;
    "ALL")
        run_all
        ;;
    *)
        exit 1
        ;;
esac
