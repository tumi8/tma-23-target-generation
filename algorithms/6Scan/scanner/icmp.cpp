/****************************************************************************
 Copyright (c) 2016-2019 Robert Beverly <rbeverly@cmand.org> all rights reserved.
 Copyright (c) 2021-2022 Bingnan Hou <houbingnan19@nudt.edu.cn> all rights reserved.
 ***************************************************************************/

#include "6scan.h"

ICMP::ICMP() :
   rtt(0), ttl(0), type(0), code(0), length(0), quote_p(0), sport(0), dport(0), ipid(0),
   probesize(0), replysize(0), replyttl(0), replytos(0), fingerprint(0)
{
    gettimeofday(&tv, NULL);
    mpls_stack = NULL;
}

ICMP4::ICMP4(struct ip *ip, struct icmp *icmp, uint32_t elapsed): ICMP()
{
    memset(&ip_src, 0, sizeof(struct in_addr));
    type = (uint8_t) icmp->icmp_type;
    code = (uint8_t) icmp->icmp_code;

    ip_src = ip->ip_src;

    replysize = ntohs(ip->ip_len);

    ipid = ntohs(ip->ip_id);
    replytos = ip->ip_tos;
    replyttl = ip->ip_ttl;
    unsigned char *ptr = NULL;

    quote = NULL;
    if (((type == ICMP_TIMXCEED) and (code == ICMP_TIMXCEED_INTRANS)) or
        (type == ICMP_UNREACH)) {
        ptr = (unsigned char *) icmp;
        quote = (struct ip *) (ptr + 8);
        quote_p = quote->ip_p;

        probesize = ntohs(quote->ip_len);

        ttl = (ntohs(quote->ip_id)) & 0xFF;
        instance = (ntohs(quote->ip_id) >> 8) & 0xFF;

        /* Original probe was TCP */
        if (quote->ip_p == IPPROTO_TCP) {
            struct tcphdr *tcp = (struct tcphdr *) (ptr + 8 + (quote->ip_hl << 2));
            rtt = elapsed - ntohl(tcp->th_seq);
            sport = ntohs(tcp->th_sport);
            dport = ntohs(tcp->th_dport);
        }

        /* Original probe was UDP */
        else if (quote->ip_p == IPPROTO_UDP) {
            struct udphdr *udp = (struct udphdr *) (ptr + 8 + (quote->ip_hl << 2));
            /* recover timestamp from UDP.check and UDP.payloadlen */
            int payloadlen = ntohs(udp->uh_ulen) - sizeof(struct icmp);
            int timestamp = udp->uh_sum;
            sport = ntohs(udp->uh_sport);
            dport = ntohs(udp->uh_dport);
            if (payloadlen > 2)
                timestamp += (payloadlen-2) << 16;
            if (elapsed >= timestamp) {
                rtt = elapsed - timestamp;
            /* checksum was 0x0000 and because of RFC, 0xFFFF was transmitted
             * causing us to see packet as being 65 (2^{16}/1000) seconds in future */
            } else if (udp->uh_sum == 0xffff) {
                timestamp = (payloadlen-2) << 16;
                rtt = elapsed - timestamp;
            }
        }

        /* Original probe was ICMP */
        else if (quote->ip_p == IPPROTO_ICMP) {
            struct icmp *icmp = (struct icmp *) (ptr + 8 + (quote->ip_hl << 2));
            uint32_t timestamp = ntohs(icmp->icmp_id);
            timestamp += ntohs(icmp->icmp_seq) << 16;
            rtt = elapsed - timestamp;
            sport = icmp->icmp_cksum;
        }

        /* According to Malone PAM 2007, 2% of replies have bad IP dst. */
        uint16_t sum = in_cksum((unsigned short *)&(quote->ip_dst), 4);

        /* Finally, does this ICMP packet have an extension (RFC4884)? */
        length = (ntohl(icmp->icmp_void) & 0x00FF0000) >> 16;
        length *= 4;
        if ( (length > 0) and (replysize > length+8) ) {
            //printf("*** ICMP Extension %d/%d\n", length, replysize);
            ptr = (unsigned char *) icmp;
            ptr += length+8;
            if (length < 128)
                ptr += (128-length);
            // ptr at start of ICMP extension
            ptr += 4;
            // ptr at start of MPLS stack header
            ptr += 2;
            // is this a class/type 1/1 (MPLS)?
            if ( (*ptr == 0x01) and (*(ptr+1) == 0x01) ) {
                ptr += 2;
                uint32_t *tmp;
                mpls_label_t *lse = (mpls_label_t *) calloc(1, sizeof(mpls_label_t) );
                mpls_stack = lse;
                for (int labels = 0; labels < MAX_MPLS_STACK_HEIGHT; labels++) {
                    tmp = (uint32_t *) ptr;
                    if (labels > 0) {
                        mpls_label_t *nextlse = (mpls_label_t *) calloc(1, sizeof(mpls_label_t) );
                        lse->next = nextlse;
                        lse = nextlse;
                    }
                    lse->label = (htonl(*tmp) & 0xFFFFF000) >> 12;
                    lse->exp   = (htonl(*tmp) & 0x00000F00) >> 8;
                    lse->ttl   = (htonl(*tmp) & 0x000000FF);
                    // bottom of stack?
                    if (lse->exp & 0x01)
                        break;
                    ptr+=4;
                }
            }
        }
    }
}

/**
 * Create ICMP6 object on received response.
 *
 * @param ip   Received IPv6 hdr
 * @param icmp Received ICMP6 hdr
 * @param elapsed Total running time
 */
ICMP6::ICMP6(struct ip6_hdr *ip, struct icmp6_hdr *icmp, uint32_t elapsed) : ICMP()
{
    is_scan = false;
    memset(&ip_src, 0, sizeof(struct in6_addr));
    type = (uint8_t) icmp->icmp6_type;
    code = (uint8_t) icmp->icmp6_code;
    ip_src = ip->ip6_src;
    replysize = ntohs(ip->ip6_plen);
    replyttl = ip->ip6_hlim;

    /* Ethernet
     * IPv6 hdr
     * ICMP6 hdr                struct icmp6_hdr *icmp; <-ptr
     *  IPv6 hdr                struct ip6_hdr *icmpip;
     *  Ext hdr                 struct ip6_ext *eh; (if present)
     *  Probe transport hdr     struct tcphdr,udphdr,icmp6_hdr;
     *  6scan payload           struct scanpayload *qpayload;
     */

    unsigned char *ptr = (unsigned char *) icmp;
    quote = (struct ip6_hdr *) (ptr + sizeof(struct icmp6_hdr));            /* Quoted IPv6 hdr */
    struct ip6_ext *eh = NULL;                /* Pointer to any extension header */
    uint16_t ext_hdr_len = 0;
    quote_p = quote->ip6_nxt;
    int offset = 0;

    /* ICMP6 echo replies only quote the 6scan payload, not the full packet! */
    if (type == ICMP6_ECHO_REPLY) {
        qpayload = (struct scanpayload *) (ptr + sizeof(struct icmp6_hdr));
    } else {
        // handle hop-by-hop (0), dest (60) and frag (44) extension headers
        if ( (quote_p == 0) or (quote_p == 44) or (quote_p == 60) ) {
            eh = (struct ip6_ext *) (ptr + sizeof(struct icmp6_hdr) + sizeof(struct ip6_hdr) );
            ext_hdr_len = 8;
            quote_p = eh->ip6e_nxt;
        }

        // continue processing
        offset = sizeof(struct icmp6_hdr) + sizeof(struct ip6_hdr) + ext_hdr_len;
        if (quote_p == IPPROTO_TCP) {
            qpayload = (struct scanpayload *) (ptr + offset + sizeof(struct tcphdr));
        } else if (quote_p == IPPROTO_UDP) {
            qpayload = (struct scanpayload *) (ptr + offset + sizeof(struct udphdr));
        } else if (quote_p == IPPROTO_ICMPV6) {
            qpayload = (struct scanpayload *) (ptr + offset + sizeof(struct icmp6_hdr));
        } else {
            warn("unknown quote");
            return;
        }
    }

    if (ntohl(qpayload->id) == 0x06536361)
        is_scan = true;
    ttl = qpayload->ttl;
    instance = qpayload->instance;
    scan_target = &(qpayload->target);
    uint32_t diff = qpayload->diff;
    if (elapsed >= diff)
        rtt = elapsed - diff;
    
    if ((type == ICMP6_TIME_EXCEEDED) or (type == ICMP6_DST_UNREACH)) {        
        probesize = ntohs(quote->ip6_plen);
        if (quote_p == IPPROTO_TCP) {
            struct tcphdr *tcp = (struct tcphdr *) (ptr + offset);
            sport = ntohs(tcp->th_sport);
            dport = ntohs(tcp->th_dport);
        } else if (quote_p == IPPROTO_UDP) {
            struct udphdr *udp = (struct udphdr *) (ptr + offset);
            sport = ntohs(udp->uh_sport);
            dport = ntohs(udp->uh_dport);
        } else if (quote_p == IPPROTO_ICMPV6) {
            struct icmp6_hdr *icmp6 = (struct icmp6_hdr *) (ptr + offset);
            sport = ntohs(icmp6->icmp6_id);
            dport = ntohs(icmp6->icmp6_seq);
        }
        uint16_t sum = in_cksum((unsigned short *)&(quote->ip6_dst), 16);
        /* IP6 dst in ICMP6 reply quote invalid! */
        if (sport != sum)            
            sport = dport = 0;
    }
}

uint32_t ICMP4::quoteDst() {
    if ((type == ICMP_TIMXCEED) and (code == ICMP_TIMXCEED_INTRANS)) {
        return quote->ip_dst.s_addr;
    }
    return 0;
}

void ICMP::printterse(char *src) {
    float r = rtt/1000.0;
    printf(">> ICMP response: %s Type: %d Code: %d TTL: %d RTT: %2.3fms", src, type, code, ttl, r);
    if (instance)
        printf(" Inst: %u", instance);
    printf("\n");
}

void ICMP::print(char *src, char *dst, int sum) {
    printf("\ttype: %d code: %d from: %s\n", type, code, src);
    printf("\t6scan instance: %u\n", instance);
    printf("\tTS: %lu.%ld\n", tv.tv_sec, (long) tv.tv_usec);
    float r = rtt/1000.0;
    printf("\tRTT: %f ms\n", r);
    printf("\tProbe dst: %s\n", dst);
    printf("\tProbe TTL: %d\n", ttl);
    if (ipid) printf("\tReply IPID: %d\n", ipid);
    if (quote_p) printf("\tQuoted Protocol: %d\n", quote_p);
    if ( (quote_p == IPPROTO_TCP) || (quote_p == IPPROTO_UDP) )
        printf("\tProbe TCP/UDP src/dst port: %d/%d\n", sport, dport);
    if ( (quote_p == IPPROTO_ICMP) || (quote_p == IPPROTO_ICMPV6) )
        printf("\tQuoted ICMP checksum: %d\n", sport);
    if (sum) printf("\tCksum of probe dst: %d\n", sum);
}


char* ICMP::getMPLS() {
    static char *mpls_label_string = (char *) calloc(1, PKTSIZE);
    static char *label = (char *) calloc(1, PKTSIZE);
    memset(mpls_label_string, 0, PKTSIZE);
    memset(label, 0, PKTSIZE);
    mpls_label_t *head = mpls_stack;
    if (not head)
        snprintf(mpls_label_string, PKTSIZE, "0");
    while (head) {
        //printf("**** LABEL: %d TTL: %d\n", head->label, head->ttl);
        if (head->next)
            snprintf(label, PKTSIZE, "%d:%d,", head->label, head->ttl);
        else
            snprintf(label, PKTSIZE, "%d:%d", head->label, head->ttl);
        strcat(mpls_label_string, label);
        head = head->next;
    }
    return mpls_label_string;
}

void
ICMP4::print() {
    char src[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &ip_src, src, INET_ADDRSTRLEN);
    char dst[INET_ADDRSTRLEN] = "no-quote";
    uint16_t sum = 0;
    if (quote) {
        inet_ntop(AF_INET, &(quote->ip_dst), dst, INET_ADDRSTRLEN);
        sum = in_cksum((unsigned short *)&(quote->ip_dst), 4);
    }
    printf("ICMP response:\n");
    ICMP::print(src, dst, sum);
    if (mpls_stack)
        printf("\t MPLS: [%s]\n", getMPLS());
    ICMP::printterse(src);
}

void
ICMP4::insert_ip_set(Stats * stats) {
    char src[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &ip_src, src, INET_ADDRSTRLEN);
    stats->IPv4.insert(src);
}

void
ICMP6::print() {
    char src[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &ip_src, src, INET6_ADDRSTRLEN);
    char dst[INET6_ADDRSTRLEN] = "no-quote";
    uint16_t sum = 0;
    if (quote != NULL) {
        inet_ntop(AF_INET6, &(quote->ip6_dst), dst, INET6_ADDRSTRLEN);
        sum = in_cksum((unsigned short *)&(quote->ip6_dst), 16);
    }
    printf("ICMP6 response from: %s type: %s\n", src, type_str.c_str());
    // ICMP::print(src, dst, sum);
    // ICMP::printterse(src);
}

void ICMP::write(FILE ** out, char *src, char *target) {
    if (*out == NULL)
        return;
    //fprintf(*out, "%s", target);
    fprintf(*out, "%s\n", src);
}

void ICMP::write_probetype(FILE ** out, char *src, char *target) {
    if (*out == NULL)
        return;
    // float r = rtt/1000.0;
    // fprintf(*out, "%s, %s, %.2fms\n", src, type_str.c_str(), r);
    fprintf(*out, "%s, %s, %s\n", src, type_str.c_str(), target);
}

void ICMP4::write(FILE ** out, Stats* stats) {
    if ((sport == 0) and (dport == 0))
        return;
    char src[INET_ADDRSTRLEN];
    char target[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &ip_src, src, INET_ADDRSTRLEN);
    inet_ntop(AF_INET, &(quote->ip_dst), target, INET_ADDRSTRLEN);
    //ICMP::write(out, src, target);
    if (strcmp(src, target) == 0)
        stats->IPv4.insert(src);
}

void ICMP6::write(FILE ** out, Stats* stats, bool probe_type) {
    char src[INET6_ADDRSTRLEN];
    char target[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &ip_src, src, INET6_ADDRSTRLEN);
    if (type == ICMP6_TIME_EXCEEDED) {
        inet_ntop(AF_INET6, &(quote->ip6_dst.s6_addr), target, INET6_ADDRSTRLEN);
        type_str = "ICMP6_TimeExceeded_";
    } else if (type == ICMP6_DST_UNREACH) {
        inet_ntop(AF_INET6, &(quote->ip6_dst.s6_addr), target, INET6_ADDRSTRLEN);
        type_str = "ICMP6_DstUnreach_";
    }
    /* In the case of an ECHO REPLY, the quote does not contain the invoking
     * packet, so we rely on the target as encoded in the 6scan payload */
    else if (type == ICMP6_ECHO_REPLY) {
        inet_ntop(AF_INET6, scan_target, target, INET6_ADDRSTRLEN);
        type_str = "ICMP6_EchoReply_";
    } 

    if (is_scan) {
        type_str += "withPayload_";
        if (strcmp(src, target) == 0) {   
            type_str += "Target";   
            if ((stats->strategy == Scan6) or (stats->strategy == Hit6)) {        
                uint64_t index = ntohl(qpayload->fingerprint);
                if (index < stats->nodelist.size())
                    stats->nodelist[index]->active++;
                else {
                    warn("Returning error regional identification %lu", index);
                    stats->baddst++;
                }
            } else if (stats->strategy == Heuristic) {               
                string addr = seed2vec(src);            
                string prefix = addr.substr(0, stats->mask/4);
                unordered_map<string, int>::iterator iter = stats->prefix_map.find(prefix);
                if (iter != stats->prefix_map.end())
                    iter->second++;
                if (addr.substr(addr.length()-4) != "1234") { // If the address is not the pseudorandom address, write it into the hitlist
                    stats->prefixes.push_back(addr);
                    ICMP::write(out, src, target);
                }
            }
        } else
            type_str += "Src";
    } else
        type_str += "noPayload";
    if (probe_type)
        ICMP::write_probetype(out, src, target);
    else
        ICMP::write(out, src, target);
}

struct in6_addr ICMP6::quoteDst6() {
    if ((type == ICMP6_TIME_EXCEEDED) and (code == ICMP6_TIME_EXCEED_TRANSIT)) {
        return quote->ip6_dst;
    }
    struct in6_addr a;
    memset(&a, 0, sizeof(struct in6_addr));
    return a;
}