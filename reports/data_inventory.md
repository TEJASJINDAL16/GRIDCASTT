# Local Data Inventory

Captured and checked 2026-11-04 IST in the original project folder. All timestamps below are UTC.

| zone   |   demand_rows | demand_from               | demand_latest             | measured_latest           |   weather_rows | weather_latest            |   weather_missing_hours |
|:-------|--------------:|:--------------------------|:--------------------------|:--------------------------|---------------:|:--------------------------|------------------------:|
| IN-NO  |         86251 | 2017-01-01 00:00:00+00:00 | 2026-11-03 18:00:00+00:00 | 2026-11-02 18:00:00+00:00 |          86088 | 2026-10-27 23:00:00+00:00 |                       0 |
| IN-WE  |         86251 | 2017-01-01 00:00:00+00:00 | 2026-11-03 18:00:00+00:00 | 2026-11-02 18:00:00+00:00 |          86088 | 2026-10-27 23:00:00+00:00 |                       0 |
| IN-SO  |         86251 | 2017-01-01 00:00:00+00:00 | 2026-11-03 18:00:00+00:00 | 2026-11-02 18:00:00+00:00 |          86088 | 2026-10-27 23:00:00+00:00 |                       0 |
| IN-EA  |         86251 | 2017-01-01 00:00:00+00:00 | 2026-11-03 18:00:00+00:00 | 2026-11-02 18:00:00+00:00 |          86088 | 2026-10-27 23:00:00+00:00 |                       0 |
| IN-NE  |         86251 | 2017-01-01 00:00:00+00:00 | 2026-11-03 18:00:00+00:00 | 2026-11-02 18:00:00+00:00 |          86088 | 2026-10-27 23:00:00+00:00 |                       0 |

Archive coverage: {'forecast_vintages': {'files': 3, 'rows': 9600, 'capture_days': 3, 'first_capture': '2026-09-08', 'latest_capture': '2026-11-03', 'positive_lead_rows': 9295}, 'demand_revisions': {'files': 3, 'rows': 10140, 'capture_days': 2, 'first_capture': '2026-09-13', 'latest_capture': '2026-11-03'}}

The September 7 to October 27 observed-weather gap was repaired without replacing older history. Demand was captured through November 3 18:00 UTC; the latest measured targets are November 2 18:00 UTC. Newer estimated targets remain unscorable. The research worktree retains its earlier frozen inputs until evaluation is complete.

These captures do not replace four to eight weeks of continuous first-settlement and forecast-error evidence. No settlement lag or weather-noise assumption was silently converted into a measurement. Local DVC pointers were updated; remote durability is not verified because Drive OAuth returns invalid_grant.
