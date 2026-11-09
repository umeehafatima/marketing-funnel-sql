-- analysis.sql  |  SQLite dialect (works in Metabase with the SQLite driver; notes for Postgres inline)

-- 1. FUNNEL BY CHANNEL: lead -> activated -> paid, with conversion rates
SELECT channel,
       COUNT(*)                                             AS leads,
       COUNT(activated_at)                                  AS activated,
       COUNT(converted_at)                                  AS paid,
       ROUND(100.0*COUNT(activated_at)/COUNT(*),1)          AS lead_to_activated_pct,
       ROUND(100.0*COUNT(converted_at)/COUNT(activated_at),1) AS activated_to_paid_pct
FROM leads
GROUP BY channel
ORDER BY paid DESC;

-- 2. UNIT ECONOMICS: spend, cost per lead, CAC, and first-year payback per channel
WITH spend AS (SELECT channel, SUM(spend) AS spend FROM campaigns GROUP BY channel),
     perf  AS (SELECT channel, COUNT(*) AS leads, COUNT(converted_at) AS customers,
                      SUM(COALESCE(mrr,0)) AS mrr FROM leads GROUP BY channel)
SELECT s.channel, ROUND(s.spend) AS spend, p.leads, p.customers,
       ROUND(s.spend/p.leads,2)                    AS cost_per_lead,
       ROUND(s.spend/NULLIF(p.customers,0),0)      AS cac,
       ROUND(12*p.mrr/s.spend,2)                   AS yr1_revenue_per_dollar
FROM spend s JOIN perf p USING(channel)
ORDER BY yr1_revenue_per_dollar DESC;

-- 3. WHAT'S QUIETLY COSTING US MONEY: campaigns that spent but produced ~nothing
SELECT c.name, c.spend, COUNT(l.lead_id) AS leads, COUNT(l.converted_at) AS paid,
       ROUND(c.spend/NULLIF(COUNT(l.converted_at),0),0) AS cost_per_customer
FROM campaigns c LEFT JOIN leads l USING(campaign_id)
GROUP BY c.campaign_id
HAVING paid <= 1 OR cost_per_customer > 3000
ORDER BY c.spend DESC;

-- 4. WHO CONVERTS: lead-to-paid by role (is "close to our user" actually true?)
SELECT role, COUNT(*) AS leads, COUNT(converted_at) AS paid,
       ROUND(100.0*COUNT(converted_at)/COUNT(*),1) AS paid_pct
FROM leads GROUP BY role ORDER BY paid_pct DESC;

-- 5. SPEED TO VALUE: days from signup to activation (window function median)
WITH d AS (
  SELECT channel, julianday(activated_at)-julianday(created_at) AS days,
         ROW_NUMBER() OVER (PARTITION BY channel ORDER BY julianday(activated_at)-julianday(created_at)) AS rn,
         COUNT(*)     OVER (PARTITION BY channel) AS n
  FROM leads WHERE activated_at IS NOT NULL)
SELECT channel, ROUND(AVG(days),1) AS median_days_to_activate
FROM d WHERE rn IN ((n+1)/2, (n+2)/2) GROUP BY channel ORDER BY 2;

-- 6. EVENT ROI: cost per attendee and per resulting customer
SELECT e.name, e.city, e.cost,
       SUM(a.attended)                                       AS attended,
       COUNT(DISTINCT CASE WHEN a.attended=1 AND l.converted_at IS NOT NULL THEN l.lead_id END) AS customers,
       ROUND(e.cost/NULLIF(SUM(a.attended),0),1)             AS cost_per_attendee
FROM events e
JOIN event_attendees a USING(event_id)
JOIN leads l USING(lead_id)
GROUP BY e.event_id ORDER BY cost_per_attendee;

-- 7. A/B TEST: landing page variant with a two-proportion z-test done in SQL
WITH t AS (SELECT variant, SUM(visitors) AS n, SUM(signups) AS x FROM landing_page_tests GROUP BY variant),
     p AS (SELECT (SELECT x FROM t WHERE variant='variant_b')*1.0/(SELECT n FROM t WHERE variant='variant_b') AS pb,
                  (SELECT x FROM t WHERE variant='control')*1.0/(SELECT n FROM t WHERE variant='control')   AS pa,
                  (SELECT n FROM t WHERE variant='variant_b') AS nb, (SELECT n FROM t WHERE variant='control') AS na,
                  (SELECT SUM(x) FROM t)*1.0/(SELECT SUM(n) FROM t) AS pp)
SELECT ROUND(100*pa,2) AS control_pct, ROUND(100*pb,2) AS variant_pct,
       ROUND(100*(pb-pa)/pa,1) AS relative_lift_pct,
       ROUND((pb-pa)/SQRT(pp*(1-pp)*(1.0/na+1.0/nb)),2) AS z_score   -- |z| > 1.96 ~ significant at 95%
FROM p;
