//
//  scanner_interface.hpp
//  6Tree
//
//  Created by Zhizhu Liu on 2019/12/12.
//

// Define scanner interface functions, parameters, variables ... in the file.

#ifndef scanner_interface_hpp
#define scanner_interface_hpp

using namespace std;

// Scan command
// In the default configuration, the scan command will be:
// zmap --probe-module=icmp6_echoscan --ipv6-target-file=targets.txt --output-file=result.txt --ipv6-source-ip=2001:----::----:1002 --bandwidth=10M --cooldown-time=4
extern string scanner_cmd;

// Scanner parameters which will be stored in _SCANNER_FILE.
#define _SI_APP_NAME "zmap" // Application name
#define _SI_DFT_INS_NUM 6 // The number of secondary instructions
#define _SI_DFT_INS_PM "--probe-module=icmp6_echoscan"
#define _SI_DFT_INS_STEP_TF "--ipv6-target-file=targets_clean.txt" // The file name should be same as _SI_STEP_TF_FILE
#define _SI_DFT_INS_STEP_RES "--output-file=result.txt" // The file name should be same as _SI_STEP_RES_FILE
#define _SI_DFT_INS_SIP "--ipv6-source-ip=2001:4ca0:108:42::28"
#define _SI_DFT_INS_BW "--rate=4000"
#define _SI_DFT_INS_CT "--cooldown-time=10"
#define _SI_DFT_INS_IF "--interface=eno3"
#define _SI_DFT_INS_GW "--gateway-mac=00:1c:73:00:00:99"

// File name of scanner parameters
#define _SCANNER_FILE "scanner_parameters"
// File name of address targets in one step
#define _SI_STEP_TF_FILE "targets.txt"
// File name of discovered active addresses in one step
#define _SI_STEP_RES_FILE "result.txt"

void si_output_scanner_command(string outdir_name);

void si_read_scanner_command(string treedir_name);

void si_write_targets(string *arr, int &arr_idx, string expression, int start_idx, int dimensionality);

void si_write_on_leaf_nodes(string *arr, int &arr_idx, struct RegionTreeNode *node);

int si_TSs_scale(struct RegionTreeNode **regn_forest, int tree_num);

int si_network_scan(struct RegionTreeNode **regn_forest, int tree_num, int &budget, ofstream &addr_total_res);

int si_adet_network_scan(string *targets, int targets_num, int &budget);

#endif /* scanner_interface_hpp */
