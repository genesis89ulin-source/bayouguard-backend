import requests 
from supabase import create_client 
import datetime 
 
SUPABASE_URL = "https://hyrqaiedlevqzbfhfxpu.supabase.co" 
SUPABASE_KEY = "sb_publishable_-nDM7hubn0soFXTqdqm-9g_EnrIxloy" 
 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) 
 
url = "https://www.harriscountyfws.org/Home/GetSiteRecentData?regionId=3&regionId=24&regionId=25&regionId=26&regionId=21&regionId=4&regionId=10&regionId=22&regionId=1&regionId=14&regionId=18&regionId=19&regionId=23&regionId=20&timeSpan=7&dt=1779069600000" 
headers = {"Referer": "https://www.harriscountyfws.org/"} 
 
response = requests.get(url, headers=headers) 
data = response.json() 
sites = data["features"] 
 
count = 0 
for site in sites: 
    props = site["properties"] 
    site_id = props.get("SiteId") 
    stream_data = props.get("StreamData") 
    if not stream_data: continue 
    stream = stream_data[0] 
    current = stream.get("CurrentLevel") 
    channel = stream.get("ChannelInfo", {}) 
    flood = channel.get("FloodLevelIndicator") 
    if flood is None: continue 
    buffer = flood - current 
    else: risk = "SAFE" 
    supabase.table("flood_gauges").insert({"gauge_id": site_id, "current_level": current, "flood_level": flood, "buffer": buffer, "risk_tier": risk}).execute() 
    count += 1 
 
print(f"{datetime.datetime.now()}: Stored {count} gauges") 
