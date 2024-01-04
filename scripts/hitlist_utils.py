import json, csv
import pytricia
import ipaddress
import time

def clean_ip2loc(cat):
    try:
        return {
            "ISP/MOB": "ISP",
            "MOB": "ISP"
        }[cat]
    except KeyError:
        return cat

def clean_peeringdb(cat):
    try:
        return {
            "Cable/DSL/ISP": "ISP",
            "Educational/Research": "Educational"
        }[cat]
    except KeyError:
        return cat

def shorten_peeringdb(cat):
    try:
        return {
            "Educational": "EDU",
            "Content": "CDN",
            "Non-Profit": "ORG",
            "Unknown": "UNK"
        }[cat]
    except KeyError:
        return cat

def load_peeringdb(fn):
    with open(fn) as f:
        peering_data = json.loads(f.read())["net"]["data"]
    return dict([(el["asn"], el["info_type"]) for el in peering_data])

def load_ip2location(fn):
    start = time.time()
    data = pytricia.PyTricia(128)
    with open(fn) as f:
        reader = csv.reader(f)
        for line in reader:
            ipfirst, iplast, cat = line[0], line[1], clean_ip2loc(line[-1])
            ipfirst = ipaddress.IPv6Address(int(ipfirst))
            iplast = ipaddress.IPv6Address(int(iplast))
            for ipnet in ipaddress.summarize_address_range(ipfirst, iplast):
                data[ipnet] = cat
    
    print(f"Loaded IP2LocationDB in {(time.time() - start) * 1000}s")
    return data

def lookup_peeringdb(asn, db, filter=True, shorten=False):
    if not isinstance(asn, int):
        try:
            asn = int(asn)
        except (ValueError, TypeError):
            ascat = "Unknown"
    
    try:
        ascat = db[asn]
    except KeyError:
        ascat = "Unknown"

    if not ascat:
        ascat = "Unknown"
    
    if filter and (not ascat in ['NSP', 'Educational/Research', 'Cable/DSL/ISP', 'Content', 'Non-Profit']):
        ascat = "Others"
    
    if shorten:
        return shorten_peeringdb(clean_peeringdb(ascat))
    return clean_peeringdb(ascat)

def lookup_ip2location(ip, db):
    return db[ip]

def lookup_cat(asn, ip, peeringdb, ip2locdb):
    return lookup_peeringdb(asn, peeringdb), lookup_ip2location(ip, ip2locdb)