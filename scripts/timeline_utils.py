import datetime, os, glob, ipaddress, binascii

def find_files(base_dir, extension, start, limit=0, end=None):
    date_start = datetime.datetime.strptime(start, "%Y-%m-%d")
    date_cur = date_start
    now = datetime.datetime.now()
    
    fps, dates = [], []
    counter = 0
    while date_cur < now:
        if limit and counter > limit:
            break
        if end and date_cur >= end:
            break
        
        date_ts = date_cur.strftime("%Y-%m-%d")
        date_mts = date_cur.strftime("%Y-%m")
        pattern1 = os.path.join(base_dir, date_mts, f"{date_ts}-{extension}.csv*")
        pattern2 = os.path.join(base_dir, f"{date_ts}-*.csv.{extension}*")
        pattern3 = os.path.join(base_dir, f"{date_ts}-{extension}.csv*")
        for pt in [pattern1, pattern2, pattern3]:
            fns = glob.glob(pt)
            if not fns:
                continue
            
            if len(fns) > 1:
                print(f"Warning, several files found for date {date_ts}")
                print(fns)
            fn = fns[0]

            if os.path.isfile(fn):
                fps.append(fn)
                dates.append(date_ts)
                counter += 1

        date_cur += datetime.timedelta(days=1)

    return dates, fps
