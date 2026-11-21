Model fire arrival vs the observed timeline of 28 Nov 2016
==========================================================

Script: scripts/compare_timeline.py (no new runs; uses ms_st09/<location>/seed_1..10, 50 runs)
Observed times: Walpole et al. (2020) NIST TN 2103, section 1.1, summarising the City of Gatlinburg After Action
Review (2017). NIST reference [11] prints a wrong DOI (it points to Baer et al. 2019, a hurricane paper);
cite the After Action Review itself once obtained.
Places: OpenStreetMap roads (data/osm_roads/roads_domain.json) traced onto the 30 m grid.
Arrival = time when 10 % of the road cells have burned (a single ember-ignited cell does not count).

place            observed  model arrival (median [min-max])  runs reaching it  mean share of road burned
Twin Creeks      11:30     12:10 [12:10 - 02:41]              13/50             21 %
Park Vista       18:08     18:13 [13:20 - 00:07]              50/50             42 %
Gatlinburg Spur  19:00     15:21 [12:52 - 17:43]              50/50             55 %
Ski Mountain Rd  19:00     not reached                         0/50              1 %

Median per spot-fire location (10 runs each):
location  Twin Creeks  Park Vista  Spur   Ski Mountain
observed  02:41 (2/10) 22:09       13:13  --
N 1 km    --           22:04       15:21  --
S 1 km    12:10        13:26       13:55  --
E 1 km    --           18:13       17:41  --
W 1 km    02:37 (1/10) 13:56       16:07  --

Notes
- The Park Vista median (+0.1 h) is a coincidence of mixing locations: S/W 1 km arrive about 4.5 h early,
  the observed and N 1 km locations about 4 h late; only E 1 km matches.
- Ski Mountain: about 1 % of road cells ever burn, 96 % of them by embers, all between 02:20 and 03:00.
- Wind at Ski Mountain, Twin Creeks and downtown is from 150-197 deg in every hour (no direction wrap there).

Update (2026-10-29): observed times now cited from the After Action Review itself
(Guthrie, Finucane, Keith and Stinnett 2017, ABS Group, for the City of Gatlinburg and Sevier County), pages:
Twin Creeks 11:30 (p.21, spot fire), Park Vista 18:08 (p.23), Spur ~19:00 (p.24),
Ski Mountain ~19:00 (p.83: fire reported a quarter mile from the bottom; was 20:00 = evacuation time before).
Ski Mountain is still not reached in any of the 50 runs.

Burned area over time: scripts/compare_burned_area.py MTBS.shp -> burned_area.png, burned_area.csv, burned_area_summary.txt
AAR acres (pp.21-28, GSMNP estimates): 500 (11:30), 2000 (15:00), 4000 (17:00), 5000 (18:00), 6000 (19:00),
7000 (20:00), 9000 (21:00), 16000 (00:00), 17000 (02:00). Model runs start at 11:00 from the spot fire, so they
lack the ~500 ac burned before; AAR minus 500 is also shown.
Result (median of 50 runs): model slower before 17:00 (15:00: 679 vs ~1500 added), then a run 17:00-19:00 that the
AAR does not show (19:00: 15,844 vs 6,000), final ~25,900 vs 17,000 ac. Inside the MTBS perimeter the model
burns only ~4,700 ac by 02:00 (MTBS 15,003 ac): the model's growth is mostly in the wrong place.
