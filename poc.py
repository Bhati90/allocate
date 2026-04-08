import requests

# 🔐 ADD YOUR AUTH HERE
HEADERS = {
    "Authorization": "Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000",
    "Content-Type": "application/json"
}

API_URL = "https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/"

# 👉 Your job IDs list
job_ids_to_check = [
    2133,1201,871,872,875,877,878,901,2058,1813,1825,1954,1885,2038,2049,
    2132,1508,884,866,870,1902,1886,2089,1893,1970,1895,1245,1997,2162,
    2163,1903,2082,1516,1774,1593,1817,1497,1591,1589,1600,1734,1752,
    1756,1894,1987,2096,2154,2034,2196,1881,1905,1889,1892,2149,1904,
    885,1513,2205,2046,1896,1879,1602,1891,2161,2047,2153,1833,1577,
    2175,1978,1512,1988,2097,2088,1964,2201,1830,2122,2200,2182,1940,
    2027,1785,2095,1824,2063,2114,1998,2199,2025,1596,2137,2173,2194,
    2343,1900,2316,1883,2479,1875,2225,2438,2398,2426,2468,2417,2107,
    2440,2224,1897,2472,2002
]

def fetch_jobs():
    response = requests.get(API_URL, headers=HEADERS)

    if response.status_code != 200:
        print("❌ API Failed:", response.status_code)
        return []

    return response.json().get("data", [])


def process_jobs(api_data):
    job_map = {}

    for job in api_data:
        job_id = job.get("id")

        visits = job.get("visits", [])
        poc_names = list(set(
            v.get("assigned_to")
            for v in visits
            if v.get("assigned_to")
        ))

        job_map[job_id] = poc_names

    return job_map


def compare_jobs(job_map):
    found = []
    not_found = []

    for jid in job_ids_to_check:
        if jid in job_map:
            found.append((jid, job_map[jid]))
        else:
            not_found.append(jid)

    return found, not_found


def main():
    print("🚀 Fetching jobs from API...")
    api_data = fetch_jobs()

    print(f"✅ Total API Jobs: {len(api_data)}")

    job_map = process_jobs(api_data)

    found, not_found = compare_jobs(job_map)

    print("\n✅ FOUND JOBS:")
    for jid, poc in found:
        print(f"Job ID: {jid} | POC: {', '.join(poc) if poc else 'No POC'}")

    print("\n❌ NOT FOUND JOBS:")
    for jid in not_found:
        print(jid)

    print(f"\n📊 Summary:")
    print(f"Found: {len(found)}")
    print(f"Not Found: {len(not_found)}")


if __name__ == "__main__":
    main()