"""Builds marketing.db: a synthetic B2B SaaS marketing funnel (seeded, reproducible).
Data is simulated -- no real company data. Run: python generate_data.py"""
import sqlite3, random, datetime as dt

random.seed(42)
DB = "marketing.db"
con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
DROP TABLE IF EXISTS campaigns; DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS events; DROP TABLE IF EXISTS event_attendees;
DROP TABLE IF EXISTS landing_page_tests;
CREATE TABLE campaigns(campaign_id INTEGER PRIMARY KEY, channel TEXT, name TEXT, start_date TEXT, spend REAL);
CREATE TABLE leads(lead_id INTEGER PRIMARY KEY, created_at TEXT, campaign_id INTEGER, channel TEXT,
  company_size TEXT, role TEXT, activated_at TEXT, converted_at TEXT, mrr REAL);
CREATE TABLE events(event_id INTEGER PRIMARY KEY, name TEXT, event_date TEXT, city TEXT, cost REAL);
CREATE TABLE event_attendees(lead_id INTEGER, event_id INTEGER, attended INTEGER);
CREATE TABLE landing_page_tests(test_date TEXT, variant TEXT, visitors INTEGER, signups INTEGER);
""")

# channel: (num_campaigns, spend/campaign, leads/campaign, activation rate, paid rate given activated, avg mrr)
CH = {
 "Paid Search":   (6, 9000, 220, 0.38, 0.10, 120),
 "Paid Social":   (5, 7000, 260, 0.22, 0.05, 90),
 "Content/SEO":   (6, 1500, 190, 0.45, 0.16, 150),
 "Newsletter":    (4, 800,  120, 0.50, 0.18, 140),
 "Community":     (4, 1200, 90,  0.58, 0.24, 180),
 "Webinar":       (4, 3000, 110, 0.40, 0.12, 160),
}
ROLES = ["Analyst","Ops","Engineer","Product","Marketing","Founder","Support"]
SIZES = ["1-10","11-50","51-200","201-1000"]
start = dt.date(2025,1,1)
cid = lid = 0
for ch,(n,spend,nleads,act,paid,mrr) in CH.items():
    for i in range(n):
        cid += 1
        d0 = start + dt.timedelta(days=random.randint(0,300))
        sp = round(spend*random.uniform(.7,1.3),2)
        if ch=="Paid Social" and i==4: sp = round(spend*1.4,2)
        cur.execute("INSERT INTO campaigns VALUES(?,?,?,?,?)",(cid,ch,f"{ch} #{i+1}",d0.isoformat(),sp))
        k = int(nleads*random.uniform(.7,1.3))
        if ch=="Paid Social" and i==4: k = 8   # a campaign that burned money
        for _ in range(k):
            lid += 1
            created = d0 + dt.timedelta(days=random.randint(0,40))
            role = random.choices(ROLES,[3,2,3,1,1,1,1])[0] if ch in("Community","Content/SEO") else random.choice(ROLES)
            size = random.choice(SIZES)
            a = c = m = None
            if random.random() < act:
                a = created + dt.timedelta(days=int(random.expovariate(1/3)))
                if random.random() < paid*(1.4 if role in("Analyst","Engineer") else 1):
                    c = a + dt.timedelta(days=random.randint(5,45)); m = round(mrr*random.uniform(.6,1.6),2)
            cur.execute("INSERT INTO leads VALUES(?,?,?,?,?,?,?,?,?)",
                (lid,created.isoformat(),cid,ch,size,role,a and a.isoformat(),c and c.isoformat(),m))

# community events: tie some existing leads to events
cities = ["San Francisco","New York","Berlin","Austin","London","Toronto"]
for e in range(1,9):
    d = start + dt.timedelta(days=random.randint(30,330))
    cur.execute("INSERT INTO events VALUES(?,?,?,?,?)",(e,f"Data Meetup {e}",d.isoformat(),random.choice(cities),random.choice([800,1500,2500,4000])))
rows = cur.execute("SELECT lead_id FROM leads").fetchall()
for e in range(1,9):
    for (l,) in random.sample(rows, random.randint(40,90)):
        cur.execute("INSERT INTO event_attendees VALUES(?,?,?)",(l,e,1 if random.random()<.55 else 0))

# A/B test: 14 days, control vs. variant (shorter hero + SQL-first copy)
for i in range(14):
    d = (dt.date(2025,10,1)+dt.timedelta(days=i)).isoformat()
    for v,p in (("control",.034),("variant_b",.041)):
        vis = random.randint(380,520)
        cur.execute("INSERT INTO landing_page_tests VALUES(?,?,?,?)",(d,v,vis,sum(random.random()<p for _ in range(vis))))
con.commit(); con.close(); print("built", DB)
