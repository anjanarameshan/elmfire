Building damage from imagery (validation data for the model's building ignition)
================================================================================
1. scripts/detect_building_damage.py MTBS.shp -> damage_auto.csv
   1,614 Microsoft footprints (captured 2019) with centroid in the MTBS perimeter; NAIP 17 Apr 2016 vs 30 Oct 2018.
   First pass: destroyed 725, survived 352, uncertain 477, new_construction 60.
   Spot check of chips: some "destroyed" are clearly the same roof (shadow / colour differences between flights),
   so the automatic labels are NOT used on their own.
2. scripts/make_review_chips.py MTBS.shp -> review/ (sheet_00..09.jpg, buildings.json), review_sample.csv
   590 buildings = all 477 uncertain + random 10 % of survived (35), destroyed (73), new_construction (6), seed 1,
   shuffled; the page is blind (it never shows the automatic label). review_sample.csv keeps the key.
3. Review page: https://claude.ai/artifact/Y8TK55eWAVmAM1iuAyR2zu (private; answers stored in its database,
   collection "labels", doc b<id>: label survived|damaged|destroyed|new|unsure, note, t).
   Cross-check rebuilt-looking houses in Google Earth historical imagery, 2 Dec 2016 (Maxar), by eye only.
4. Review finished (590/590, 31 min, median 1.9 s per building). Answers: review_answers/labels/*.json
   survived 331, destroyed 174, new 37, damaged 27, unsure 21.
   Auto label check (random confident sample): auto-survived -> 31/35 survived; auto-destroyed -> 47/72 destroyed
   (9 survived, 9 not built in 2016).
5. scripts/validate_damage.py -> validation/ (validation_summary.txt, validation_buildings.csv, validation.png)
   AUC 0.56 [0.48-0.64]; the model gets the overall loss level roughly right where houses are sparse but
   over-predicts loss in dense areas, and its site-factor directions are opposite to the observed ones.
6. Batch 2 (make_review_chips.py MTBS.shp batch2): the other 1,024 footprints + 60 blind repeats of batch 1
   (sheet2_*.jpg, buildings2.json, review_sample2.csv; collection "labels2", split by field h so each query < 1,000).
   Finished; answers in review_answers/labels2/ (b<id> = new building, r<id> = repeat).
   All 1,614 footprints: survived 984, destroyed 369, damaged 35, new 158, unsure 68.
   validate_damage.py now uses the full census (weight 1) and reports the repeat check:
     repeats: same label 40/60 (67 %), kappa 0.33; 11 of the 20 changes are destroyed -> survived, 0 the other way.
     auto-destroyed buildings called destroyed: batch 1 47/72 (65 %); batch 2 by save order 41 %, 38 %, 22 %, 26 %, 17 %.
   => the labels drift towards "survived" over the session (likely houses rebuilt by Oct 2018 read as survivors).
   The full-census numbers (AUC 0.54, observed burned share 0.29) are NOT final until the contested labels are
   checked against imagery taken just after the fire (Google Earth 2 Dec 2016) or the county damage assessment.
